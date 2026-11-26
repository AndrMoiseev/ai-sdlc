package apply

import (
	"fmt"
	"path/filepath"
	"sort"
	"strings"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/agent"
)

func documentPaths(basis mapping) ([]string, error) {
	paths := []string{"proposal.md", "design.md", "tasks.md"}
	if workKind(basis) == "change" {
		root := str(basis["project_root"])
		relative, err := filepath.Rel(root, str(basis["change_root"]))
		if err != nil {
			return nil, err
		}
		prefix := filepath.ToSlash(relative) + "/"
		tracked, err := gitBytes(root, "ls-tree", "-r", "--name-only", "-z", "HEAD")
		if err != nil {
			return nil, err
		}
		for _, name := range strings.Split(string(tracked), "\x00") {
			if strings.HasPrefix(name, prefix+"specs/") && strings.HasSuffix(name, "/spec.md") {
				paths = append(paths, strings.TrimPrefix(name, prefix))
			}
		}
	}
	sort.Strings(paths)
	return paths, nil
}

func explorerBasis(state, task mapping, kind, stage, directory string) (mapping, error) {
	if task == nil && kind != "research" {
		return nil, reject("assignment_scope", "Checks require a task scope")
	}
	source, err := snapshot(state, taskRoot(state, task))
	if err != nil {
		return nil, err
	}
	return explorerBasisAtSource(state, task, source, kind, directory)
}

func explorerBasisAtSource(state, task, source mapping, kind, directory string) (mapping, error) {
	basis := object(state["basis"])
	paths, err := documentPaths(basis)
	if err != nil {
		return nil, err
	}
	result := mapping{"run_id": state["run_id"], "change_id": state["change_id"], "source": source,
		"manifest": digest(mapping{"head": basis["head"], "document_paths": paths})}
	if kind == "checks" {
		checks, err := registryChecks(state, task, directory)
		if err != nil {
			return nil, err
		}
		result["registry_revision"] = intValue(object(task["check_registry"])["revision"])
		result["checks"] = checks
	}
	return result, nil
}

func meaningful(value any) bool { return strings.TrimSpace(str(value)) != "" }

func nonemptyStrings(value any) bool {
	items := array(value)
	if len(items) == 0 {
		return false
	}
	for _, value := range items {
		if !meaningful(value) {
			return false
		}
	}
	return true
}

func validateAssignmentShape(assignment mapping) error {
	if assignment == nil {
		return fmt.Errorf("Explorer assignment must be an object")
	}
	if !meaningful(assignment["id"]) {
		return fmt.Errorf("Explorer assignment requires id")
	}
	kind := str(assignment["kind"])
	if kind != "research" && kind != "checks" {
		return fmt.Errorf("Explorer kind must be research or checks")
	}
	scope := object(assignment["scope"])
	if len(scope) != 3 {
		return fmt.Errorf("Explorer scope requires project, work and task (null when absent)")
	}
	for _, key := range []string{"project", "work", "task"} {
		value, exists := scope[key]
		if !exists {
			return fmt.Errorf("Explorer scope requires project, work and task (null when absent)")
		}
		if value != nil && !meaningful(value) {
			return fmt.Errorf("Explorer scope values must be identities or null")
		}
	}
	if len(object(assignment["basis"])) == 0 {
		return fmt.Errorf("Explorer assignment requires a nonempty basis")
	}
	for _, key := range []string{"read_scope", "outputs"} {
		if !nonemptyStrings(assignment[key]) {
			return fmt.Errorf("Explorer assignment requires %s", key)
		}
	}
	if len(object(assignment["limits"])) == 0 {
		return fmt.Errorf("Explorer assignment requires explicit limits")
	}
	if kind == "research" {
		if !meaningful(assignment["question"]) {
			return fmt.Errorf("Research requires a question")
		}
		if _, exists := assignment["check_ids"]; exists {
			return fmt.Errorf("Research cannot execute check_ids")
		}
		return nil
	}
	if !nonemptyStrings(assignment["check_ids"]) {
		return fmt.Errorf("Checks require exact check_ids")
	}
	ids := map[string]bool{}
	for _, id := range stringArray(assignment["check_ids"]) {
		if ids[id] {
			return fmt.Errorf("Checks require unique check_ids")
		}
		ids[id] = true
	}
	if _, question := assignment["question"]; question {
		return fmt.Errorf("Checks use check_ids, not a research question")
	}
	if !meaningful(assignment["stage"]) {
		return fmt.Errorf("Checks require a stage")
	}
	if revision, ok := integer(assignment["registry_revision"]); !ok || revision < 0 {
		return fmt.Errorf("Checks require a nonnegative registry_revision")
	}
	return nil
}

func validateExplorerAssignment(state, task, role mapping, directory string) error {
	assignment := object(role["assignment"])
	if err := validateAssignmentShape(assignment); err != nil {
		return err
	}
	if assignment["id"] != role["role_id"] {
		return reject("assignment_id", "Assignment ID is the registered role ID")
	}
	taskID := object(task["plan"])["id"]
	expectedScope := mapping{"project": object(state["basis"])["project_root"], "work": state["change_id"], "task": taskID}
	if digest(assignment["scope"]) != digest(expectedScope) {
		return reject("assignment_scope", "Assignment must name this project, work and task scope")
	}
	kind, stage := str(assignment["kind"]), str(assignment["stage"])
	if kind == "checks" && (task == nil || !includes([]string{"baseline", "self", "independent", "integration"}, stage)) {
		return reject("assignment_stage", "Use an applicable task stage")
	}
	basis, err := explorerBasis(state, task, kind, stage, directory)
	if err != nil {
		return err
	}
	if digest(assignment["basis"]) != digest(basis) {
		return reject("assignment_basis", "Assignment requires the current source, manifest and registry")
	}
	capabilities := []string{"launch", "read", "write_artifacts"}
	if kind == "checks" {
		ids := []string{}
		for _, check := range array(basis["checks"]) {
			ids = append(ids, str(object(check)["id"]))
		}
		if digest(assignment["check_ids"]) != digest(ids) || intValue(assignment["registry_revision"]) != intValue(basis["registry_revision"]) {
			return reject("assignment_checks", "Assign the complete exact check set and registry revision")
		}
		capabilities = append(capabilities, "run_command")
	}
	observed := object(object(role["capabilities"])["observations"])
	if observed == nil {
		return fmt.Errorf("Capability observations must be an object")
	}
	problems := []string{}
	for _, capability := range capabilities {
		item := object(observed[capability])
		reason, trace := "", any(nil)
		switch {
		case item == nil:
			reason = "Capability was not observed"
		case item["available"] != true:
			reason, trace = orText(item["reason"], "Capability is unavailable or unconfirmed"), item["trace"]
		case !meaningful(item["trace"]):
			reason = "Capability has no host evidence trace"
		default:
			continue
		}
		problems = append(problems, fmt.Sprintf("{'capability': %s, 'reason': %s, 'trace': %s}", pythonQuote(capability), pythonQuote(reason), pythonRepr(trace)))
	}
	if len(problems) != 0 {
		return reject("host_limits", "Explorer capability unavailable: ["+strings.Join(problems, ", ")+"]")
	}
	return nil
}

func authorizeExplorer(state, task mapping, roleID, stage, directory string, active, current bool) (mapping, error) {
	role := object(object(state["roles"])[roleID])
	if role["kind"] != "explorer" || role["task_id"] != object(task["plan"])["id"] ||
		role["status"] != "active" && (active || role["status"] != "finished") {
		return nil, reject("role_unavailable", "Active independent explorer with matching scope required")
	}
	assignment := object(role["assignment"])
	if assignment["kind"] != "checks" || assignment["stage"] != stage {
		return nil, reject("assignment_stage", "Explorer must hold a checks assignment for this exact stage")
	}
	if current {
		if err := validateExplorerAssignment(state, task, role, directory); err != nil {
			return nil, err
		}
	}
	return role, nil
}

func copyMapping(value mapping) mapping {
	result := make(mapping, len(value))
	for key, field := range value {
		result[key] = field
	}
	return result
}

func roleEvent(state, task, event mapping, directory string) (any, error) {
	payload := object(event["payload"])
	kind := str(event["type"])
	roles := object(state["roles"])
	roleID := str(payload["role_id"])
	registered := object(roles[roleID])
	research := task == nil && (kind == "role_register" && payload["kind"] == "explorer" && object(payload["assignment"])["kind"] == "research" ||
		kind == "role_result" && object(registered["assignment"])["kind"] == "research")
	if task == nil && !research {
		return nil, reject("task_required", "Only research explorers use null task scope")
	}
	taskID := object(task["plan"])["id"]
	if kind == "role_result" {
		if registered == nil || registered["task_id"] != taskID || registered["status"] != "active" {
			return nil, reject("role_missing", "Active registered role required")
		}
		if !truth(payload["result"]) || !truth(payload["trace"]) {
			return nil, reject("role_result", "Result and host trace required")
		}
		if registered["kind"] == "explorer" && object(registered["assignment"])["kind"] == "research" {
			result := object(payload["result"])
			if result["kind"] != "research" || !meaningful(result["answer"]) {
				return nil, reject("research_result", "Research result requires kind and answer")
			}
			for _, field := range []string{"references", "inspected_scope", "limitations", "assumptions", "questions"} {
				if array(result[field]) == nil {
					return nil, reject("research_result", "Research result requires "+field)
				}
			}
			if !truth(result["inspected_scope"]) {
				return nil, reject("research_result", "Record the inspected scope")
			}
		}
		registered["status"], registered["result"], registered["trace"] = "finished", payload["result"], payload["trace"]
		return mapping{"role_finished": roleID, "task_status": task["status"]}, nil
	}
	for _, field := range []string{"role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"} {
		if _, ok := payload[field]; !ok {
			return nil, reject("role_schema", "Host context and launch evidence required")
		}
	}
	roleKind := str(payload["kind"])
	if !includes([]string{"executor", "reviewer", "explorer"}, roleKind) || payload["fresh"] != true {
		return nil, reject("fresh_role", "A fresh context is mandatory")
	}
	if roleKind == "reviewer" && !includes([]string{"verification", "code"}, str(payload["lens_id"])) {
		return nil, reject("review_lens", "Assign exactly one required review lens")
	}
	host := str(payload["host"])
	if !includes([]string{"codex", "claude-code"}, host) || !truth(payload["launch_ref"]) || !truth(payload["context_id"]) {
		return nil, reject("host_evidence", "Record actual host launch; do not simulate a role")
	}
	if _, duplicate := roles[roleID]; duplicate {
		return nil, reject("duplicate_role", "Role already registered")
	}
	if !eventID.MatchString(roleID) {
		return nil, reject("role_id", "Use a filesystem-safe role ID")
	}
	basis := object(state["basis"])
	project := str(basis["project_root"])
	settings, err := agent.SettingsSource(project)
	if err != nil {
		return nil, err
	}
	selection := object(payload["agent_selection"])
	if payload["agent_selection"] == nil && settings != nil {
		return nil, reject("agent_selection_missing", "Resolve the role from project settings before launching and registering it")
	}
	if payload["agent_selection"] != nil {
		if err := agent.ValidateSelection(selection, project, "sdd-apply."+roleKind, host); err != nil {
			return nil, err
		}
	}
	if roleKind == "executor" && writerActive(state, task) {
		return nil, reject("writer_active", "Finish or reconcile the previous executor before assigning another")
	}
	for _, raw := range roles {
		other := object(raw)
		if digest(other["context_id"]) != digest(payload["context_id"]) {
			continue
		}
		if other["kind"] != "explorer" || roleKind != "explorer" || other["task_id"] != taskID || other["status"] != "finished" || other["host"] != host {
			return nil, reject("context_reused", "Only completed explorer assignments of the same task may share a context; every reviewer starts fresh")
		}
		if selection != nil || other["agent_selection"] != nil {
			previous := object(other["agent_selection"])
			if previous == nil || selection == nil || digest(selectionIdentity(selection)) != digest(selectionIdentity(previous)) {
				return nil, reject("agent_selection_conflict", "Different agent selections require separate fresh contexts")
			}
		}
	}
	if object(payload["capabilities"])["fresh_context"] != true {
		return nil, reject("host_limits", "Fresh context mechanism unavailable; distinguish busy slots from unsupported host")
	}
	if roleKind == "explorer" {
		if err := validateExplorerAssignment(state, task, payload, directory); err != nil {
			return nil, err
		}
	}
	role := copyMapping(payload)
	role["task_id"], role["status"], role["registered_at"], role["registered_revision"] = taskID, "active", now(), intValue(state["revision"])+1
	roles[roleID] = role
	sources := mapping{}
	paths, err := documentPaths(basis)
	if err != nil {
		return nil, err
	}
	for _, path := range paths {
		sources[path] = filepath.Join(str(basis["change_root"]), filepath.FromSlash(path))
	}
	packet := mapping{"task": nil, "project_root": project, "execution_directory": directory, "role": role, "sources": sources}
	if roleKind == "explorer" {
		packet["assignment"] = role["assignment"]
	}
	if !research {
		task["roles"] = append(array(task["roles"]), roleID)
		for _, field := range []string{"paths", "worktree", "checks", "blockers"} {
			packet[field] = task[field]
		}
		packet["task"], packet["prior_commits"], packet["rejected_approaches"] = task["plan"], task["commits"], []any{}
		if value, exists := task["rejected_approaches"]; exists {
			packet["rejected_approaches"] = value
		}
		if roleKind == "reviewer" && payload["lens_id"] == "verification" {
			verification, err := verificationPacket(state, task, directory, stageFor(task))
			if err != nil {
				return nil, err
			}
			packet["verification"] = verification
		}
		if worktree := object(task["worktree"]); worktree != nil {
			selection := copyMapping(worktree)
			delete(selection, "snapshot")
			delete(selection, "inventory")
			packet["worktree"] = selection
			packet["worktree_state"] = mapping{"path": "state.json", "task_id": taskID}
		}
		if workKind(basis) == "refactoring" {
			context, err := refactoringContext(state, task, directory)
			if err != nil {
				return nil, err
			}
			packet["work_kind"], packet["refactoring"] = "refactoring", context
		}
		effects, err := pendingEffects(directory, state, "worktree_refresh")
		if err != nil {
			return nil, err
		}
		for _, record := range effects {
			request := object(record["request"])
			if request["task_id"] != taskID {
				continue
			}
			saved := object(request["precondition"])
			patch := saved["patch"]
			if patch == nil {
				artifact, err := contained(str(saved["artifacts"]), "task.patch")
				if err != nil {
					return nil, err
				}
				patch = artifact
			}
			packet["worktree_recovery"] = mapping{"intent_id": object(request["event"])["event_id"], "source": object(saved["old"])["path"], "replacement": saved["new"], "patch": patch}
		}
	}
	path, err := contained(directory, filepath.Join("runs", str(state["run_id"]), "roles", roleID+".json"))
	if err != nil {
		return nil, err
	}
	if err := writeJSON(path, packet); err != nil {
		return nil, err
	}
	return mapping{"role": role, "packet": path}, nil
}

func selectionIdentity(selection mapping) mapping {
	identity := selectFields(selection, "host", "mode", "launch")
	identity["definition_sha256"] = object(selection["definition"])["sha256"]
	return identity
}
