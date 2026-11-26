package setup

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"unicode/utf8"

	"github.com/BurntSushi/toml"
	"go.yaml.in/yaml/v3"
)

//go:embed assets/defaults.json
var defaultRoles []byte

var roleNames = []string{
	"sdd-spec.architect", "sdd-spec.explorer", "sdd-apply.explorer",
	"sdd-spec.reviewer", "sdd-spec.editor", "sdd-apply.executor", "sdd-apply.reviewer",
}

var frontmatter = regexp.MustCompile(`(?ms)^---\r?\n(.*?)^---[ \t]*(?:\r?\n|$)(.*)\z`)

func textValue(value any) bool {
	text, ok := value.(string)
	return ok && text != "" && strings.TrimSpace(text) == text &&
		!strings.ContainsFunc(text, func(char rune) bool { return char < 32 })
}

func configuredRoles(project string) (object, any, error) {
	path := filepath.Join(project, ".sdd", "settings.json")
	raw, err := optionalBytes(path)
	if err != nil || raw == nil {
		return object{}, nil, err
	}
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return nil, nil, err
	}
	settings := asObject(value)
	if settings == nil {
		return nil, nil, errors.New("settings.json must contain an object")
	}
	if settings["schema_version"] != json.Number("1") {
		return nil, nil, errors.New("settings.json requires schema_version: 1")
	}
	agents := object{}
	if value, exists := settings["subagents"]; exists {
		agents = asObject(value)
		if agents == nil {
			return nil, nil, errors.New("subagents must be an object")
		}
	}
	roles := object{}
	for key, value := range agents {
		if key != "roles" {
			return nil, nil, errors.New("Unknown subagents field; supported: roles")
		}
		roles = asObject(value)
		if roles == nil {
			return nil, nil, errors.New("subagents.roles must be an object")
		}
	}
	for role, name := range roles {
		if !slices.Contains(roleNames, role) {
			return nil, nil, fmt.Errorf("Unknown SDD role: %s", role)
		}
		if text := asString(name); text == "" || strings.TrimSpace(text) != text {
			return nil, nil, fmt.Errorf("Agent name for %s must be a nonempty string", role)
		}
	}
	return roles, object{"path": resolve(path), "sha256": digest(raw)}, nil
}

func rolePresets() object {
	value, _ := decodeJSON(defaultRoles, nil)
	return asObject(asObject(value)["roles"])
}

func sharedEvidence(explicit, legacy string) (string, string, error) {
	if explicit != "" && legacy != "" {
		return "", "", errors.New("Choose sdd_shared or legacy sdd_spec, not both")
	}
	if explicit == "" && legacy == "" {
		binary, err := os.Executable()
		if err != nil {
			return "", "", err
		}
		explicit = filepath.Join(filepath.Dir(resolve(binary)), "sdd-shared")
	} else if explicit == "" {
		explicit = filepath.Join(filepath.Dir(resolve(legacy)), "sdd-shared")
	}
	root := resolve(explicit)
	api, err := readJSON(filepath.Join(root, "api.json"))
	if err != nil {
		return "", "", fmt.Errorf("Install matching sdd-shared alongside the consumer or supply sdd_shared: %s", root)
	}
	if asObject(api)["api_version"] != json.Number("2") {
		return "", "", fmt.Errorf("Incompatible sdd-shared API; expected 2: %s", root)
	}
	schemas := asObject(asObject(asObject(api)["document_schemas"])["change"])
	for _, kind := range []string{"state", "review", "decisions"} {
		if !equal(schemas[kind], []any{2}) {
			return "", "", fmt.Errorf("sdd-shared does not support change checkpoint formats v2; install the matching SDD bundle: %s", root)
		}
	}
	required := []string{"SKILL.md", "scripts/sdd_shared/__init__.py"}
	for _, name := range []string{"check", "snapshot", "resolve_agent", "checkpoint"} {
		required = append(required, "scripts/"+name+".py", "scripts/"+name+".py.lock")
	}
	for _, name := range []string{"documents", "paths", "validation", "snapshots", "reviews", "subagents", "checkpoints", "checkpoint_git"} {
		required = append(required, "scripts/sdd_shared/"+name+".py")
	}
	for _, path := range required {
		if !isFile(filepath.Join(root, path)) {
			return "", "", fmt.Errorf("Incomplete sdd-shared package: %s", root)
		}
	}
	raw, err := os.ReadFile(filepath.Join(root, "scripts", "sdd_shared", "subagents.py"))
	if err != nil {
		return "", "", err
	}
	return root, digest(raw), nil
}

func inspectCommand(args arguments) (object, error) {
	var available any
	if args.has("available-agents") {
		var err error
		available, err = readJSON(args.value("available-agents"))
		if err != nil {
			return nil, err
		}
	}
	return inspectProject(args.value("project-root"), args.value("host"), args.value("sdd-shared"),
		args.value("sdd-spec"), args.value("user-agent-dir"), available, args.values("names"))
}

func inspectProject(root, host, shared, legacy, userDirectory string, available any, requested []string) (object, error) {
	if host != "codex" && host != "claude-code" {
		return nil, errors.New("Supported hosts: codex, claude-code")
	}
	project, err := projectDirectory(root, "project_root must be a directory")
	if err != nil {
		return nil, err
	}
	shared, contract, err := sharedEvidence(shared, legacy)
	if err != nil {
		return nil, err
	}
	roles, settings, err := configuredRoles(project)
	if err != nil {
		return nil, err
	}
	names := sortedUnique(requested)
	for _, name := range names {
		if !textValue(name) {
			return nil, errors.New("names must contain agent names")
		}
	}
	hostDirectory := ".codex"
	var hostAgents []string
	if host == "claude-code" {
		hostDirectory = ".claude"
		switch available.(type) {
		case []any, []string:
			hostAgents = sortedUnique(stringsIn(available))
		default:
			return nil, errors.New("Claude Code needs available_agents from the current host catalog, not a disk-derived list")
		}
		for _, name := range hostAgents {
			if !textValue(name) {
				return nil, errors.New("Claude Code needs available_agents from the current host catalog, not a disk-derived list")
			}
		}
		available = hostAgents
	} else if available != nil {
		return nil, errors.New("available_agents is only supported for Claude Code")
	}
	if userDirectory == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, err
		}
		base := filepath.Join(home, hostDirectory)
		if host == "codex" {
			if configured, ok := os.LookupEnv("CODEX_HOME"); ok {
				base = configured
			}
		}
		userDirectory = filepath.Join(base, "agents")
	}
	userDirectory = resolve(userDirectory)
	local, localEvidence, err := scanAgents(filepath.Join(project, hostDirectory, "agents"), host, "project")
	if err != nil {
		return nil, err
	}
	catalog, evidence, err := scanAgents(userDirectory, host, "user")
	if err != nil {
		return nil, err
	}
	for name, entry := range local {
		catalog[name] = entry
	}
	for path, hash := range localEvidence {
		evidence[path] = hash
	}
	presets := rolePresets()
	requested = append([]string{}, names...)
	roleRows := make([]object, 0, len(roleNames))
	for _, role := range roleNames {
		preset := asObject(presets[role])
		current, present := roles[role]
		if present {
			requested = append(requested, asString(current))
		}
		requested = append(requested, asString(preset["agent"]))
		roleRows = append(roleRows, object{"role": role, "present": present, "current": current,
			"default": preset["agent"], "profile_default": preset[host]})
	}
	agents := object{}
	for _, name := range sortedUnique(requested) {
		entry := catalog[name]
		if entry == nil {
			entry = object{"name": name, "scope": "missing", "path": nil, "model": nil, "effort": nil, "sha256": nil}
		}
		if host == "claude-code" {
			entry["available"] = slices.Contains(hostAgents, name)
			if entry["available"] == true && entry["scope"] == "missing" {
				entry["scope"] = "native"
			}
		}
		agents[name] = entry
	}
	result := object{
		"schema_version": 1, "project_root": project, "host": host,
		"inputs": object{"project_root": project, "host": host, "sdd_shared": shared,
			"user_agent_dir": userDirectory, "available_agents": available, "names": names},
		"roles": roleRows, "agents": agents,
		"evidence": object{"settings": settings, "agents": evidence, "contract": contract, "defaults": digest(defaultRoles)},
	}
	result["snapshot"] = identity(result)
	return result, nil
}

func sortedUnique(values []string) []string {
	result := append([]string{}, values...)
	slices.Sort(result)
	return slices.Compact(result)
}

func scanAgents(root, host, scope string) (map[string]object, object, error) {
	records, evidence := map[string]object{}, object{}
	entries, err := os.ReadDir(root)
	if errors.Is(err, os.ErrNotExist) {
		return records, evidence, nil
	}
	if err != nil {
		return nil, nil, err
	}
	paths := []string{}
	if host == "claude-code" {
		err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
			if err == nil && strings.HasSuffix(entry.Name(), ".md") && path != root {
				paths = append(paths, path)
			}
			return err
		})
		if err != nil {
			return nil, nil, err
		}
	} else {
		for _, entry := range entries {
			if strings.EqualFold(filepath.Ext(entry.Name()), ".toml") {
				paths = append(paths, filepath.Join(root, entry.Name()))
			}
		}
	}
	slices.Sort(paths)
	for _, path := range paths {
		raw, err := os.ReadFile(path)
		if err != nil {
			return nil, nil, err
		}
		data, _, err := parseAgent(raw, host, path)
		if err != nil {
			return nil, nil, err
		}
		name := asString(data["name"])
		if records[name] != nil {
			return nil, nil, fmt.Errorf("Duplicate agent name %s in %s", pythonString(name), root)
		}
		hash := digest(raw)
		evidence[resolve(path)] = hash
		records[name] = object{"name": name, "scope": scope, "path": absolute(path), "model": data["model"],
			"effort": data[effortField(host)], "sha256": hash}
	}
	return records, evidence, nil
}

func effortField(host string) string {
	if host == "codex" {
		return "model_reasoning_effort"
	}
	return "effort"
}

func parseAgent(raw []byte, host, path string) (object, string, error) {
	raw = unbom(raw)
	if !utf8.Valid(raw) {
		return nil, "", fmt.Errorf("Invalid UTF-8 agent definition: %s", path)
	}
	data := object{}
	body := ""
	if host == "codex" {
		if _, err := toml.Decode(string(raw), &data); err != nil {
			return nil, "", err
		}
	} else {
		match := frontmatter.FindStringSubmatch(string(raw))
		if match == nil || !strings.HasPrefix(string(raw), "---") {
			return nil, "", fmt.Errorf("Invalid agent frontmatter: %s", path)
		}
		if err := yaml.Unmarshal([]byte(match[1]), &data); err != nil {
			return nil, "", err
		}
		body = match[2]
	}
	if data == nil {
		return nil, "", fmt.Errorf("Agent must contain a mapping: %s", path)
	}
	if !textValue(data["name"]) || !textValue(data["description"]) {
		return nil, "", fmt.Errorf("Agent requires name and description: %s", path)
	}
	if host == "codex" {
		if _, ok := data["developer_instructions"].(string); !ok {
			return nil, "", fmt.Errorf("Missing developer_instructions: %s", path)
		}
	} else if strings.TrimSpace(body) == "" {
		return nil, "", fmt.Errorf("Missing agent instructions: %s", path)
	}
	for _, field := range []string{"model", effortField(host)} {
		if value, present := data[field]; present && !textValue(value) {
			return nil, "", fmt.Errorf("Invalid %s: %s", field, path)
		}
	}
	return data, body, nil
}
