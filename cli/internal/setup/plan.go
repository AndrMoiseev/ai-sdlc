package setup

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/pmezard/go-difflib/difflib"
)

const (
	agentDescription  = "SDD worker for an explicitly assigned specification or implementation role."
	agentInstructions = "Follow the SDD role contract, task scope, source paths and output format supplied " +
		"by the parent. Read the referenced role instructions before acting. Work only on " +
		"the assigned task. For review and verification, report evidence and findings; " +
		"change implementation files only when the assigned role explicitly authorizes it. " +
		"Report missing inputs and failed checks accurately."
)

var (
	sha256Pattern  = regexp.MustCompile(`^[0-9a-f]{64}$`)
	newAgentName   = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)
	linesWithEnd   = regexp.MustCompile(`[^\r\n\v\f\x1c-\x1e\x{85}\x{2028}\x{2029}]*(?:\r\n|[\r\n\v\f\x1c-\x1e\x{85}\x{2028}\x{2029}]|$)`)
	tomlAssignment = regexp.MustCompile(`^[ \t]*([A-Za-z0-9_-]+|"(?:[^"\\\r\n]|\\.)*"|'[^'\r\n]*')[ \t]*=[ \t]*`)
	yamlProfile    = regexp.MustCompile(`^(model|effort)(:[ \t]*)(.*?)([ \t]+#.*)?(\r?\n)?$`)
)

func planCommand(args arguments) (object, error) {
	path := resolve(args.value("request"))
	value, err := readJSON(path)
	if err != nil {
		return nil, err
	}
	request := asObject(value)
	if request == nil {
		return nil, errors.New("Request must be a JSON object")
	}
	_, hasFile := request["inspection_file"]
	_, hasHash := request["inspection_sha256"]
	if hasFile || hasHash {
		if !objectFields(request, "inspection_file", "inspection_sha256", "roles", "agents") {
			return nil, errors.New("Use inspection OR inspection_file with inspection_sha256, roles and agents")
		}
		source, expected := asString(request["inspection_file"]), asString(request["inspection_sha256"])
		if strings.TrimSpace(source) == "" {
			return nil, errors.New("inspection_file must be a file path")
		}
		if !sha256Pattern.MatchString(expected) {
			return nil, errors.New("inspection_sha256 must be the SHA-256 returned by inspect --output")
		}
		source = resolve(anchored(filepath.Dir(path), source))
		if isDir(source) {
			return nil, errors.New("inspection_file must be a JSON file")
		}
		raw, err := os.ReadFile(source)
		if err != nil {
			return nil, fileError(err)
		}
		if digest(raw) != expected {
			return nil, errors.New("Inspection file changed; inspect again and reconcile choices")
		}
		inspection, err := decodeJSON(raw, nil)
		if err != nil {
			return nil, err
		}
		request = object{"inspection": inspection, "roles": request["roles"], "agents": request["agents"]}
	}
	return makePlan(request)
}

func decide(value, current, fallback any, label string) (any, error) {
	choice := asObject(value)
	if choice == nil {
		return nil, fmt.Errorf("Explicit decision required for %s", label)
	}
	action := asString(choice["action"])
	if !slices.Contains([]string{"keep", "default", "set"}, action) {
		return nil, fmt.Errorf("Invalid decision for %s", label)
	}
	fields := []string{"action"}
	if action == "set" {
		fields = append(fields, "value")
	}
	if !objectFields(choice, fields...) {
		return nil, fmt.Errorf("Unexpected fields for %s", label)
	}
	switch action {
	case "default":
		current = fallback
	case "set":
		current = choice["value"]
	}
	if current != nil && !textValue(current) {
		return nil, fmt.Errorf("Invalid value for %s", label)
	}
	return current, nil
}

func profileDefaults(presets object, roles []string, host string) object {
	first := asObject(asObject(presets[roles[0]])[host])
	for _, role := range roles[1:] {
		if !equal(first, asObject(presets[role])[host]) {
			return nil
		}
	}
	return first
}

func makePlan(request object) (object, error) {
	if !objectFields(request, "inspection", "roles", "agents") {
		return nil, errors.New("Request requires inspection, roles and agents only")
	}
	previous := asObject(request["inspection"])
	inputs := asObject(previous["inputs"])
	if inputs == nil {
		return nil, errors.New("Provide the inspect result")
	}
	current, err := inspectProject(asString(inputs["project_root"]), asString(inputs["host"]), asString(inputs["sdd_shared"]),
		"", asString(inputs["user_agent_dir"]), inputs["available_agents"], stringsIn(inputs["names"]))
	if err != nil {
		return nil, err
	}
	if !equal(previous, current) {
		return nil, errors.New("Project or agent catalog changed; inspect again and reconcile choices")
	}
	choices := asObject(request["roles"])
	if !objectFields(choices, roleNames...) {
		return nil, errors.New("Decide every role exactly once")
	}
	selected, byAgent := object{}, map[string][]string{}
	for _, row := range current["roles"].([]object) {
		role := asString(row["role"])
		if row["present"] == false && equal(choices[role], object{"action": "keep"}) {
			return nil, fmt.Errorf("%s is missing; accept its default or choose a value", role)
		}
		name, err := decide(choices[role], row["current"], row["default"], role)
		if err != nil {
			return nil, err
		}
		if name != nil {
			selected[role] = name
			byAgent[asString(name)] = append(byAgent[asString(name)], role)
		}
	}
	agentChoices := asObject(request["agents"])
	if agentChoices == nil || !objectFields(agentChoices, keys(byAgent)...) {
		return nil, errors.New("Decide model and effort for every distinct selected agent")
	}
	project, host := asString(current["project_root"]), asString(current["host"])
	operations, warnings := []object{}, []string{}
	addOperation := func(relative, after string) error {
		path, err := safeTarget(project, relative)
		if err != nil {
			return err
		}
		before, err := optionalBytes(path)
		if err != nil || bytes.Equal(before, []byte(after)) {
			return err
		}
		if !utf8.Valid(before) {
			return fmt.Errorf("Invalid UTF-8 in %s", path)
		}
		beforeText := string(unbom(before))
		diff, err := difflib.GetUnifiedDiffString(difflib.UnifiedDiff{
			A: diffLines(beforeText), B: diffLines(after), Context: 3, FromFile: relative, ToFile: relative,
		})
		if err != nil {
			return err
		}
		var beforeValue, beforeHash any
		if before != nil {
			beforeValue, beforeHash = beforeText, digest(before)
		}
		operations = append(operations, object{"path": filepath.ToSlash(relative), "before_sha256": beforeHash,
			"before": beforeValue, "after": after, "after_sha256": digest([]byte(after)), "diff": diff})
		return nil
	}
	presets := rolePresets()
	for _, name := range keys(byAgent) {
		entry := asObject(asObject(current["agents"])[name])
		if entry == nil {
			return nil, fmt.Errorf("Inspect again with --names %s before selecting a new name", name)
		}
		decision := asObject(agentChoices[name])
		if !objectFields(decision, "model", "effort") {
			return nil, fmt.Errorf("Decide model and effort for %s", name)
		}
		defaults := profileDefaults(presets, byAgent[name], host)
		scope := entry["scope"]
		for _, field := range []string{"model", "effort"} {
			choice := asObject(decision[field])
			if choice == nil {
				return nil, fmt.Errorf("Decision missing for %s.%s", name, field)
			}
			if choice["action"] == "default" && defaults == nil {
				return nil, fmt.Errorf("Roles sharing %s have different presets; choose one explicit model and effort", name)
			}
			if choice["action"] == "keep" {
				if scope == "missing" {
					return nil, fmt.Errorf("%s.%s is missing; accept its default or choose a value", name, field)
				}
				if scope != "native" && entry[field] == nil {
					return nil, fmt.Errorf("%s.%s is unset; accept its default or explicitly choose inheritance with null", name, field)
				}
			}
		}
		if scope == "native" {
			keep := object{"action": "keep"}
			if !equal(decision["model"], keep) || !equal(decision["effort"], keep) {
				return nil, fmt.Errorf("%s is host-managed: keep it or choose a new project agent name", name)
			}
			warnings = append(warnings, name+": native definition retained; model/effort unavailable from the name-only host catalog")
			continue
		}
		model, err := decide(decision["model"], entry["model"], defaults["model"], name+".model")
		if err != nil {
			return nil, err
		}
		effort, err := decide(decision["effort"], entry["effort"], defaults["effort"], name+".effort")
		if err != nil {
			return nil, err
		}
		if scope != "missing" && model == entry["model"] && effort == entry["effort"] {
			continue
		}
		if effort != nil {
			allowed := []string{"low", "medium", "high", "xhigh", "max"}
			if host == "codex" {
				allowed = append(allowed, "none", "minimal", "ultra")
			}
			if !slices.Contains(allowed, asString(effort)) {
				if host == "claude-code" {
					return nil, errors.New("Unsupported Claude effort; choose low, medium, high, xhigh, max or null")
				}
				return nil, errors.New("Unsupported Codex effort")
			}
		}
		var relative string
		var raw []byte
		if scope == "project" {
			relative, err = filepath.Rel(project, asString(entry["path"]))
			if err != nil {
				return nil, err
			}
		} else {
			if !newAgentName.MatchString(name) {
				return nil, fmt.Errorf("New project agent names must match [a-z][a-z0-9-] (max 64): %s", name)
			}
			if host == "codex" {
				relative = filepath.Join(".codex", "agents", name+".toml")
			} else {
				relative = filepath.Join(".claude", "agents", name+".md")
			}
			target, err := safeTarget(project, relative)
			if err != nil {
				return nil, err
			}
			existing, err := optionalBytes(target)
			if err != nil {
				return nil, err
			}
			if existing != nil {
				return nil, fmt.Errorf("Agent filename already occupied: %s", relative)
			}
		}
		if path := asString(entry["path"]); path != "" {
			raw, err = os.ReadFile(path)
			if err != nil {
				return nil, fileError(err)
			}
		}
		after, err := renderAgent(raw, host, name, asString(model), asString(effort))
		if err != nil {
			return nil, err
		}
		if err := addOperation(relative, after); err != nil {
			return nil, err
		}
		if scope == "user" {
			warnings = append(warnings, name+": create a project override; personal definition remains unchanged")
		}
	}
	_, rawSettings, settings, order, err := settingsFile(project)
	if err != nil {
		return nil, err
	}
	beforeSettings := identity(settings)
	agents := asObject(settings["subagents"])
	if agents == nil {
		agents = object{}
		settings["subagents"] = agents
	}
	agents["roles"] = selected
	order["/subagents/roles"] = roleNames
	if rawSettings == nil || beforeSettings != identity(settings) {
		if err := addOperation(".sdd/settings.json", jsonText(settings, true, order)+"\n"); err != nil {
			return nil, err
		}
	}
	if host == "claude-code" {
		warnings = append(warnings, "Verify selected names and their effective definitions in the live host catalog after writing. Reload/restart if needed; disk discovery does not prove native precedence or model availability.")
	} else {
		warnings = append(warnings, "SDD imports only model and model_reasoning_effort from Codex profiles; task instructions come from the SDD role contract.")
	}
	warnings = append(warnings, "Presets are recommendations, not proof of model access or model/effort compatibility. No model was launched.")
	result := object{"schema_version": 1, "request": request, "operations": operations, "selected_roles": selected, "warnings": warnings}
	result["plan_id"] = identity(result)
	return result, nil
}

func diffLines(text string) []string {
	result := linesWithEnd.FindAllString(text, -1)
	if len(result) > 0 && result[len(result)-1] == "" {
		return result[:len(result)-1]
	}
	return result
}

func renderAgent(raw []byte, host, name, model, effort string) (string, error) {
	if host == "codex" {
		if model == "inherit" {
			model = ""
		}
		if raw == nil {
			raw = []byte("name = " + jsonText(name, false, nil) + "\ndescription = " + jsonText(agentDescription, false, nil) +
				"\ndeveloper_instructions = " + jsonText(agentInstructions, false, nil) + "\n")
		}
		content := editTOMLProfile(string(unbom(raw)), model, effort)
		data, _, err := parseAgent([]byte(content), host, name)
		if err != nil {
			return "", err
		}
		for key, value := range map[string]string{"model": model, "model_reasoning_effort": effort} {
			actual, present := data[key]
			if value == "" && present || value != "" && actual != value {
				return "", fmt.Errorf("Rendered Codex profile does not apply %s for %s", key, name)
			}
		}
		return content, nil
	}
	if model == "" {
		model = "inherit"
	}
	header, body := "name: "+name+"\ndescription: "+agentDescription+"\n", "\n"+agentInstructions+"\n"
	if raw != nil {
		match := frontmatter.FindSubmatch(unbom(raw))
		header, body = string(match[1]), string(match[2])
	}
	content := "---\n" + editYAMLProfile(header, model, effort) + "---\n" + body
	_, _, err := parseAgent([]byte(content), host, name)
	return content, err
}

func editTOMLProfile(content, model, effort string) string {
	var result strings.Builder
	expected := map[string]string{"model": model, "model_reasoning_effort": effort}
	blankStart := 0
	offset := 0
	for offset < len(content) {
		begin := offset
		remaining := content[begin:]
		if strings.HasPrefix(strings.TrimLeft(remaining, " \t"), "[") {
			break
		}
		offset = tomlStatementEnd(content, begin)
		statement := content[begin:offset]
		match := tomlAssignment.FindStringSubmatchIndex(statement)
		if match != nil {
			key := tomlKey(statement[match[2]:match[3]])
			if value, exists := expected[key]; exists {
				delete(expected, key)
				if value != "" {
					valueEnd := tomlStringEnd(statement, match[1])
					result.WriteString(statement[:match[1]])
					result.WriteString(jsonText(value, false, nil))
					result.WriteString(statement[valueEnd:])
					blankStart = result.Len()
				}
				continue
			}
		}
		result.WriteString(statement)
		if strings.TrimSpace(statement) != "" {
			blankStart = result.Len()
		}
	}
	prior := result.String()
	var insertion strings.Builder
	for _, key := range []string{"model", "model_reasoning_effort"} {
		if value := expected[key]; value != "" {
			fmt.Fprintf(&insertion, "%s = %s\n", key, jsonText(value, false, nil))
		}
	}
	if insertion.Len() == 0 {
		return prior + content[offset:]
	}
	before, trailing := prior[:blankStart], prior[blankStart:]
	if before != "" && !strings.HasSuffix(before, "\n") {
		before += "\n"
	}
	if trailing == "" && offset < len(content) {
		trailing = "\n"
	}
	return before + insertion.String() + trailing + content[offset:]
}

func tomlKey(raw string) string {
	switch raw[0] {
	case '\'':
		return raw[1 : len(raw)-1]
	case '"':
		key, _ := strconv.Unquote(raw)
		return key
	default:
		return raw
	}
}

// The original profile has already been parsed. Scan its statements to locate
// the profile fields while preserving comments, unrelated values and tables.
func tomlStatementEnd(text string, start int) int {
	depth := 0
	for offset := start; offset < len(text); {
		switch text[offset] {
		case '"', '\'':
			offset = tomlStringEnd(text, offset)
			continue
		case '#':
			if end := strings.IndexByte(text[offset:], '\n'); end >= 0 {
				offset += end
				continue
			}
			return len(text)
		case '[', '{':
			depth++
		case ']', '}':
			depth--
		case '\n':
			if depth == 0 {
				return offset + 1
			}
		}
		offset++
	}
	return len(text)
}

func tomlStringEnd(text string, start int) int {
	if start >= len(text) {
		return len(text)
	}
	quote := text[start]
	multiline := start+2 < len(text) && text[start+1] == quote && text[start+2] == quote
	offset := start + 1
	if multiline {
		offset += 2
	}
	for offset < len(text) {
		if text[offset] == '\\' && quote == '"' {
			offset += 2
			continue
		}
		if text[offset] != quote {
			offset++
			continue
		}
		if !multiline {
			return offset + 1
		}
		end := offset + 1
		for end < len(text) && text[end] == quote {
			end++
		}
		if end-offset >= 3 {
			return end
		}
		offset = end
	}
	return len(text)
}

func editYAMLProfile(content, model, effort string) string {
	var result strings.Builder
	expected := map[string]string{"model": model, "effort": effort}
	for _, line := range diffLines(content) {
		match := yamlProfile.FindStringSubmatch(line)
		if match != nil {
			value, exists := expected[match[1]]
			if !exists {
				result.WriteString(line)
				continue
			}
			delete(expected, match[1])
			if value != "" {
				if match[3] != "" && match[3][0] == '"' && yamlProfileScalar(value, match[3]) == match[3] ||
					strings.Trim(match[3], "'") == value {
					result.WriteString(line)
				} else {
					fmt.Fprintf(&result, "%s%s%s%s%s", match[1], match[2], yamlProfileScalar(value, match[3]), match[4], match[5])
				}
			}
			continue
		}
		result.WriteString(line)
	}
	for _, key := range []string{"model", "effort"} {
		if value := expected[key]; value != "" {
			if text := result.String(); text != "" && !strings.HasSuffix(text, "\n") {
				result.WriteByte('\n')
			}
			fmt.Fprintf(&result, "%s: %s\n", key, yamlProfileScalar(value, ""))
		}
	}
	return result.String()
}

func yamlProfileScalar(value, previous string) string {
	if strings.HasPrefix(previous, "'") && !strings.ContainsRune(value, '\'') {
		return "'" + value + "'"
	}
	if strings.HasPrefix(previous, "\"") || strings.ContainsAny(value, ":#{}[],") ||
		slices.Contains([]string{"true", "false", "null", "~"}, value) {
		return jsonText(value, false, nil)
	}
	return value
}

func planSummary(plan object) object {
	request := asObject(plan["request"])
	inspection := asObject(request["inspection"])
	byAgent := map[string][]string{}
	selected := asObject(plan["selected_roles"])
	for _, role := range roleNames {
		if name := asString(selected[role]); name != "" {
			byAgent[name] = append(byAgent[name], role)
		}
	}
	selectedAgents := object{}
	presets := rolePresets()
	for name, roles := range byAgent {
		entry := asObject(asObject(inspection["agents"])[name])
		defaults := profileDefaults(presets, roles, asString(inspection["host"]))
		decision := asObject(asObject(request["agents"])[name])
		model, _ := decide(decision["model"], entry["model"], defaults["model"], name+".model")
		effort, _ := decide(decision["effort"], entry["effort"], defaults["effort"], name+".effort")
		scope := entry["scope"]
		if scope == "missing" || model != entry["model"] || effort != entry["effort"] {
			scope = "project"
		}
		selectedAgents[name] = object{"roles": roles, "scope": scope, "model": model, "effort": effort}
	}
	operations := []object{}
	for _, row := range plan["operations"].([]object) {
		operations = append(operations, object{"path": row["path"], "diff": row["diff"]})
	}
	return object{"project_root": inspection["project_root"], "host": inspection["host"], "plan_id": plan["plan_id"],
		"selected_roles": selected, "selected_agents": selectedAgents, "warnings": plan["warnings"], "operations": operations}
}
