// Package agent resolves role selections from the project and host catalogs.
package agent

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"github.com/BurntSushi/toml"
)

var Roles = []string{"sdd-spec.architect", "sdd-spec.explorer", "sdd-apply.explorer", "sdd-spec.reviewer", "sdd-spec.editor", "sdd-apply.executor", "sdd-apply.reviewer"}

type object = map[string]any

func cleanText(v any) bool { s, ok := v.(string); return ok && s != "" && s == strings.TrimSpace(s) }
func absolute(path string) string {
	p, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	if r, e := filepath.EvalSymlinks(p); e == nil {
		return r
	}
	return p
}
func evidence(path string, b []byte) object {
	return object{"path": absolute(path), "sha256": fmt.Sprintf("%x", sha256.Sum256(b))}
}
func decodeValue(d *json.Decoder) (any, error) {
	t, err := d.Token()
	if err != nil {
		return nil, err
	}
	switch t {
	case json.Delim('{'):
		m := object{}
		for d.More() {
			k, err := d.Token()
			if err != nil {
				return nil, err
			}
			name := k.(string)
			if _, ok := m[name]; ok {
				return nil, fmt.Errorf("Duplicate JSON key: %s", name)
			}
			v, err := decodeValue(d)
			if err != nil {
				return nil, err
			}
			m[name] = v
		}
		_, err = d.Token()
		return m, err
	case json.Delim('['):
		a := []any{}
		for d.More() {
			v, err := decodeValue(d)
			if err != nil {
				return nil, err
			}
			a = append(a, v)
		}
		_, err = d.Token()
		return a, err
	}
	return t, nil
}
func fromJSON(b []byte) (any, error) {
	d := json.NewDecoder(bytes.NewReader(bytes.TrimPrefix(b, []byte{0xef, 0xbb, 0xbf})))
	d.UseNumber()
	v, err := decodeValue(d)
	if err == nil {
		if _, e := d.Token(); e != io.EOF {
			return nil, errors.New("Unexpected trailing JSON data")
		}
	}
	return v, err
}
func mapping(m object, k, msg string) (object, error) {
	if v, ok := m[k]; ok {
		if o, ok := v.(map[string]any); ok {
			return o, nil
		}
		return nil, errors.New(msg)
	}
	return object{}, nil
}
func settings(root string) (object, any, string, error) {
	p := filepath.Join(root, ".sdd", "settings.json")
	b, e := os.ReadFile(p)
	if os.IsNotExist(e) {
		return object{}, nil, "settings_missing", nil
	}
	if e != nil {
		return nil, nil, "", e
	}
	v, e := fromJSON(b)
	if e != nil {
		return nil, nil, "", e
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, nil, "", errors.New("settings.json must contain an object")
	}
	if m["schema_version"] != json.Number("1") {
		return nil, nil, "", errors.New("settings.json requires schema_version: 1")
	}
	agents, e := mapping(m, "subagents", "subagents must be an object")
	if e != nil {
		return nil, nil, "", e
	}
	for k := range agents {
		if k != "roles" {
			return nil, nil, "", errors.New("Unknown subagents field; supported: roles")
		}
	}
	roles, e := mapping(agents, "roles", "subagents.roles must be an object")
	if e != nil {
		return nil, nil, "", e
	}
	for role, name := range roles {
		if !slices.Contains(Roles, role) {
			return nil, nil, "", fmt.Errorf("Unknown SDD role: %s", role)
		}
		if !cleanText(name) {
			return nil, nil, "", fmt.Errorf("Agent name for %s must be a nonempty string", role)
		}
	}
	return roles, evidence(p, b), "role_unmapped", nil
}
func definitions(project, user, name string) (object, object, error) {
	for _, dir := range []string{filepath.Join(project, ".codex", "agents"), user} {
		entries, e := os.ReadDir(dir)
		if os.IsNotExist(e) {
			continue
		}
		if e != nil {
			return nil, nil, e
		}
		var found, source object
		for _, file := range entries {
			if !strings.EqualFold(filepath.Ext(file.Name()), ".toml") {
				continue
			}
			path := filepath.Join(dir, file.Name())
			b, e := os.ReadFile(path)
			if e != nil {
				return nil, nil, e
			}
			m := object{}
			if _, e = toml.Decode(string(bytes.TrimPrefix(b, []byte{0xef, 0xbb, 0xbf})), &m); e != nil {
				return nil, nil, fmt.Errorf("Invalid agent TOML %s: %v", path, e)
			}
			if m["name"] == name {
				if found != nil {
					return nil, nil, fmt.Errorf("Duplicate agent name '%s' in %s", name, dir)
				}
				found = m
				source = evidence(path, b)
				source["name"] = name
			}
		}
		if found != nil {
			if !cleanText(found["description"]) {
				return nil, nil, fmt.Errorf("%v: description is required", source["path"])
			}
			if _, ok := found["developer_instructions"].(string); !ok {
				return nil, nil, fmt.Errorf("%v: developer_instructions is required", source["path"])
			}
			return found, source, nil
		}
	}
	return nil, nil, nil
}
func Resolve(project, role, host string, opts map[string]any) (map[string]any, error) {
	project = absolute(project)
	info, e := os.Stat(project)
	if e != nil {
		return nil, e
	}
	if !info.IsDir() {
		return nil, errors.New("project_root must be a directory")
	}
	if !slices.Contains(Roles, role) {
		return nil, fmt.Errorf("Unknown SDD role: %s", role)
	}
	if host != "codex" && host != "claude-code" {
		return nil, fmt.Errorf("Unsupported host: %s", host)
	}
	model, effort := opts["parent_model"], opts["parent_effort"]
	inherit, _ := opts["native_inheritance"].(bool)
	if v, ok := opts["native_inheritance"]; ok && v != true && v != false {
		return nil, errors.New("native_inheritance must be a boolean")
	}
	if inherit && model != nil {
		return nil, errors.New("Choose observed parent_model or confirmed native_inheritance, not both")
	}
	if !inherit && (!cleanText(model) || model == "inherit") {
		return nil, errors.New("Provide the observed parent's exact model ID or confirm native_inheritance")
	}
	if effort != nil && !cleanText(effort) {
		return nil, errors.New("Invalid parent_effort")
	}
	roles, source, reason, e := settings(project)
	if e != nil {
		return nil, e
	}
	name, _ := roles[role].(string)
	launch := object{}
	var userPath, catalog any
	if host == "codex" {
		dir, ok := opts["user_agent_dir"].(string)
		if !ok {
			codex, ok := os.LookupEnv("CODEX_HOME")
			if !ok {
				home, _ := os.UserHomeDir()
				codex = filepath.Join(home, ".codex")
			}
			dir = filepath.Join(codex, "agents")
		}
		userPath = absolute(dir)
	} else {
		catalog = opts["available_agents"]
	}
	result := object{"schema_version": 1, "project_root": project, "role": role, "host": host, "requested_agent": roles[role], "mode": "parent", "reason": reason, "settings": source, "definition": nil, "launch": launch, "warnings": []string{}, "resolution": object{"parent_model": model, "parent_effort": effort, "native_inheritance": inherit, "user_agent_dir": userPath, "available_agents": catalog}}
	if host == "claude-code" {
		available, ok := catalog.([]any)
		if !ok {
			return nil, errors.New("Claude Code requires available_agents from its actual tool/catalog")
		}
		for _, v := range available {
			if !cleanText(v) {
				return nil, errors.New("Claude Code requires available_agents from its actual tool/catalog")
			}
		}
		if name != "" && slices.Contains(available, any(name)) {
			result["mode"] = "native-agent"
			result["reason"] = "agent_available"
			launch["subagent_type"] = name
			return result, nil
		}
		if !slices.Contains(available, any("general-purpose")) {
			return nil, errors.New("No selected agent or general-purpose fallback is available; restore host capability")
		}
		launch["subagent_type"] = "general-purpose"
		if model != nil {
			launch["model"] = model
		}
	} else {
		launch["fork_turns"] = "none"
		if model != nil {
			launch["model"] = model
		}
		if effort != nil {
			launch["reasoning_effort"] = effort
		}
		if name != "" {
			data, def, e := definitions(project, userPath.(string), name)
			if e != nil {
				return nil, e
			}
			if def != nil {
				m, ok := data["model"]
				if !ok {
					m = "inherit"
				}
				if !cleanText(m) {
					return nil, errors.New("Agent model must be a nonempty string")
				}
				f := data["model_reasoning_effort"]
				if f != nil && !cleanText(f) {
					return nil, errors.New("Agent model_reasoning_effort must be a nonempty string")
				}
				if m != "inherit" {
					launch["model"] = m
				}
				if f != nil {
					launch["reasoning_effort"] = f
				} else if launch["model"] != model {
					delete(launch, "reasoning_effort")
				}
				ignored := []string{}
				for k := range data {
					if !slices.Contains([]string{"name", "description", "model", "model_reasoning_effort"}, k) {
						ignored = append(ignored, k)
					}
				}
				slices.Sort(ignored)
				def["ignored_fields"] = ignored
				result["definition"] = def
				result["mode"] = "model-profile"
				result["reason"] = "agent_profile"
				result["warnings"] = []string{"Only model and model_reasoning_effort are applied; agent instructions, tools, skills and other settings are not imported. Use the SDD role contract."}
				return result, nil
			}
		}
	}
	if name != "" {
		result["reason"] = "agent_missing"
		result["warnings"] = []string{fmt.Sprintf("Agent '%s' unavailable; using the parent model", name)}
	}
	return result, nil
}
func Run(args []string, stdout, stderr io.Writer) int {
	flags := flag.NewFlagSet("resolve-agent", flag.ContinueOnError)
	flags.SetOutput(stderr)
	project := flags.String("project-root", "", "Project directory")
	role := flags.String("role", "", "SDD role")
	host := flags.String("host", "", "Host")
	opts := object{}
	for _, k := range []string{"parent-model", "parent-effort", "user-agent-dir"} {
		flags.Func(k, k, func(v string) error { opts[strings.ReplaceAll(k, "-", "_")] = v; return nil })
	}
	inherit := flags.Bool("native-inheritance", false, "Use host inheritance")
	agents := flags.String("available-agents", "", "Host catalog JSON file")
	if e := flags.Parse(args); e != nil {
		if e == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if flags.NArg() != 0 || *project == "" || !slices.Contains(Roles, *role) || (*host != "codex" && *host != "claude-code") || (*inherit == (opts["parent_model"] != nil)) {
		flags.Usage()
		return 2
	}
	opts["native_inheritance"] = *inherit
	var e error
	if *agents != "" {
		var b []byte
		b, e = os.ReadFile(*agents)
		if e == nil {
			opts["available_agents"], e = fromJSON(b)
		}
	}
	var result object
	if e == nil {
		result, e = Resolve(*project, *role, *host, opts)
	}
	enc := json.NewEncoder(stdout)
	if e != nil {
		enc.Encode(object{"ok": false, "code": "subagent_configuration", "message": e.Error()})
		return 1
	}
	enc.Encode(object{"ok": true, "result": result})
	return 0
}
