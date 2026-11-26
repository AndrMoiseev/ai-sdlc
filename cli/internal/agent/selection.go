package agent

import (
	"encoding/json"
	"errors"
	"os"
)

func SettingsSource(project string) (any, error) {
	_, source, _, err := settings(absolute(project))
	return source, err
}

func same(a, b any) bool {
	x, e := json.Marshal(a)
	y, f := json.Marshal(b)
	return e == nil && f == nil && string(x) == string(y)
}

// ValidateSelection re-resolves the role at registration so changed settings,
// changed definitions and a different host catalog cannot reuse an attestation.
func ValidateSelection(s map[string]any, project, role, host string) error {
	if s == nil {
		return errors.New("agent_selection must be the resolver result")
	}
	project = absolute(project)
	roles, src, _, err := settings(project)
	if err != nil {
		return err
	}
	if !same(s["schema_version"], 1) || s["role"] != role || s["host"] != host || s["project_root"] != project {
		return errors.New("Agent selection belongs to another role, host or project")
	}
	if !same(s["settings"], src) || !same(s["requested_agent"], roles[role]) {
		return errors.New("Agent settings changed before registration; reconcile the launch before proceeding")
	}
	launch, ok := s["launch"].(map[string]any)
	if !ok {
		return errors.New("Agent selection requires launch parameters")
	}
	inputs, _ := s["resolution"].(map[string]any)
	if len(inputs) != 5 {
		return errors.New("Agent selection requires its resolution inputs")
	}
	for _, k := range []string{"parent_model", "parent_effort", "native_inheritance", "user_agent_dir", "available_agents"} {
		if _, ok := inputs[k]; !ok {
			return errors.New("Agent selection requires its resolution inputs")
		}
	}
	model, has := launch["model"]
	selected := has && cleanText(model) || !has && inputs["native_inheritance"] == true
	mode := s["mode"]
	if host == "codex" {
		if (mode != "parent" && mode != "model-profile") || launch["fork_turns"] != "none" || !selected {
			return errors.New("Invalid Codex launch selection")
		}
	} else {
		if (mode != "parent" && mode != "native-agent") || !cleanText(launch["subagent_type"]) {
			return errors.New("Invalid Claude Code launch selection")
		}
		if mode == "parent" && (launch["subagent_type"] != "general-purpose" || !selected) {
			return errors.New("Invalid parent fallback")
		}
		if mode == "native-agent" && (launch["subagent_type"] != roles[role] || has) {
			return errors.New("Native agent selection must preserve the definition's model")
		}
	}
	if mode == "model-profile" {
		def, _ := s["definition"].(map[string]any)
		path, _ := def["path"].(string)
		if !cleanText(path) {
			return errors.New("Model profile requires definition evidence")
		}
		b, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if evidence(path, b)["sha256"] != def["sha256"] {
			return errors.New("Agent definition changed before registration; reconcile the launch")
		}
	}
	actual, err := Resolve(project, role, host, inputs)
	if err != nil {
		return err
	}
	if !same(s, actual) {
		return errors.New("Agent catalog or launch selection changed before registration; reconcile the launch")
	}
	return nil
}
