package apply

import (
	"fmt"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
)

var eventID = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)
var gitOID = regexp.MustCompile(`^(?:[0-9a-f]{40}|[0-9a-f]{64})$`)

func applyEventAndRender(directory string, raw any) (any, error) {
	path, err := resolvePath(directory)
	if err != nil {
		return nil, err
	}
	result, err := withLock(path, func() (any, error) {
		return applyEvent(path, raw)
	})
	if err != nil {
		return nil, err
	}
	e := &execution{directory: directory}
	packed, err := e.pack(result, "", true)
	if err != nil {
		return nil, err
	}
	view, err := renderDirectory(directory)
	if err != nil {
		return mapping{"event_result": packed, "view_error": err.Error(), "recovery": "Run dashboard; do not repeat Git operations"}, nil
	}
	return mapping{"event_result": packed, "view": view}, nil
}

func applyEvent(directory string, raw any) (any, error) {
	e, err := openExecution(directory)
	if err != nil {
		return nil, err
	}
	manifest := e.manifest
	event := object(raw)
	if len(event) != 6 {
		return nil, reject("event_schema", "Expected the complete typed event envelope")
	}
	for _, key := range []string{"event_id", "run_id", "expected_revision", "type", "task_id", "payload"} {
		if _, exists := event[key]; !exists {
			return nil, reject("event_schema", "Expected the complete typed event envelope")
		}
	}
	id := str(event["event_id"])
	if !eventID.MatchString(id) {
		return nil, reject("event_id", "Use a filesystem-safe event ID")
	}
	entry, err := e.lookup(manifest["event_index"], id)
	if err != nil {
		return nil, err
	}
	revision := intValue(manifest["revision"])
	if entry != nil {
		if str(entry["fingerprint"]) != digest(event) {
			return nil, reject("event_conflict", "Event ID reused with another payload")
		}
		if intValue(entry["revision"]) > revision {
			return nil, reject("history_corrupt", "Event is not committed")
		}
		return e.hydrate(entry["result"], make(map[string]bool))
	}
	if str(event["run_id"]) != str(manifest["run_id"]) {
		return nil, reject("run_mismatch", "Wrong execution run")
	}
	expected, valid := integer(event["expected_revision"])
	if !valid || expected != revision {
		return nil, reject("revision_conflict", "Re-read current state")
	}
	state, err := e.readState()
	if err != nil {
		return nil, err
	}
	if event["task_id"] != nil && object(state["tasks"])[str(event["task_id"])] == nil {
		return nil, reject("unknown_task", "Unknown TASK-ID")
	}
	kind := str(event["type"])
	if kind == "resume" || kind == "finalize" {
		if _, err := e.audit(); err != nil {
			return nil, err
		}
	}
	result, err := reduce(state, event, directory)
	if err != nil {
		return nil, err
	}
	task := object(object(state["tasks"])[str(event["task_id"])])
	if kind == "commit" || kind == "revised_plan" || kind == "candidate" && truth(object(task["worktree"])["integrated"]) {
		head, err := gitText(str(object(state["basis"])["project_root"]), "rev-parse", "HEAD")
		if err != nil {
			return nil, err
		}
		state["execution_head"] = head
	}
	state["revision"] = revision + 1
	state["updated_at"] = now()
	if kind == "check_run" && task != nil && object(event["payload"])["stage"] == "baseline" {
		task["baseline_event"] = mapping{"event_id": id, "log": object(result)["log"]}
	}
	if err := e.appendEvent(state, event, result); err != nil {
		return nil, err
	}
	if err := e.save(state); err != nil {
		return nil, err
	}
	return result, nil
}

func reduce(state, event mapping, directory string) (any, error) {
	kind := str(event["type"])
	taskID := str(event["task_id"])
	task := object(object(state["tasks"])[taskID])
	payload := object(event["payload"])
	if payload == nil {
		return nil, reject("payload", "Object required")
	}
	switch kind {
	case "block":
		return blockExecution(state, task, payload)
	case "budget_extend":
		return extendBudget(state, task, payload)
	case "spec_conflict":
		return recordSpecConflict(state, event, directory)
	}
	switch kind {
	case "role_result", "review_result", "role_register", "verification_result", "finalize", "resume", "revised_plan":
	default:
		if state["status"] != "active" || truth(state["blockers"]) {
			return nil, reject("run_blocked", pythonRepr(state["blockers"]))
		}
	}
	if kind != "role_result" && kind != "resume" && kind != "revised_plan" {
		basis := object(state["basis"])
		if _, legacy := basis["manifest"]; legacy || intValue(basis["schema_version"]) != 2 {
			return nil, reject("basis_migration", "Reconcile legacy document manifests into the current execution basis")
		}
		if !gitOID.MatchString(str(basis["head"])) {
			return nil, reject("basis_commit", "Execution basis needs its admission commit OID")
		}
	}
	switch kind {
	case "worktree_refresh", "worktree_refresh_resolve", "role_register", "role_result":
	default:
		if task != nil {
			effects, err := pendingEffects(directory, state, "worktree_refresh")
			if err != nil {
				return nil, err
			}
			for _, effect := range effects {
				request := object(effect["request"])
				if request["task_id"] == taskID {
					return nil, reject("refresh_pending", "Finish the pending worktree refresh before continuing this task")
				}
			}
		}
	}
	if kind == "role_register" && state["status"] != "active" {
		predecessor := object(object(state["roles"])[str(payload["successor_of"])])
		allowed := predecessor["status"] == "lost" && predecessor["task_id"] == event["task_id"]
		for _, value := range array(state["blockers"]) {
			allowed = allowed && object(value)["reason"] == "lost_role"
		}
		if !allowed {
			return nil, reject("run_blocked", "Only a lost-role successor may be registered while blocked")
		}
	}
	switch kind {
	case "start":
		return startTask(state, task, taskID, payload, directory)
	case "repair":
		return repairTask(state, task, payload)
	case "worktree_create", "worktree_remove":
		return transitionWorktree(state, task, event, directory)
	case "candidate":
		return candidateEvent(state, task, event, directory)
	case "checks_register", "checks_extend", "checks_revise", "check_setup", "check_run", "procedure_begin", "procedure_result":
		return verificationEvent(state, task, event, directory)
	case "role_register", "role_result":
		return roleEvent(state, task, event, directory)
	case "review_start", "review_result":
		if task == nil {
			return nil, reject("task_required", "Only research explorers use null task scope")
		}
		if kind == "review_start" {
			return startReview(state, task, event, directory)
		}
		return reviewResult(state, task, event, directory)
	case "verification_result":
		return verificationResultEvent(state, task, event, directory)
	case "worktree_refresh", "worktree_refresh_resolve", "transfer", "integrate":
		return gitTransition(state, task, event, directory)
	case "commit", "accept":
		return commitEvent(state, task, event, directory)
	case "resume", "revised_plan", "finalize":
		return recoveryEvent(state, task, event, directory)
	default:
		return nil, fmt.Errorf("unknown_event: %s", kind)
	}
}

func recordSpecConflict(state, event mapping, directory string) (any, error) {
	payload := object(event["payload"])
	if !truth(payload["reproduction"]) || !truth(payload["criteria"]) || !truth(payload["contract"]) {
		return nil, reject("conflict_evidence", "Record reproduction, AC and conflicting contract")
	}
	material, err := contained(directory, filepath.Join("runs", str(state["run_id"]), "spec-return", str(event["event_id"])+".json"))
	if err != nil {
		return nil, err
	}
	record := mapping{"task_id": event["task_id"], "change_root": object(state["basis"])["change_root"]}
	for key, value := range payload {
		record[key] = value
	}
	if err := writeJSON(material, record); err != nil {
		return nil, err
	}
	state["blockers"] = append(array(state["blockers"]), mapping{"reason": "spec_conflict", "task_id": event["task_id"],
		"resume_condition": "Revised approved plan and execution instruction", "material": material})
	state["status"] = "blocked"
	return mapping{"return_to": "sdd-spec", "material": material}, nil
}

func blockExecution(state, task, payload mapping) (any, error) {
	if !truth(payload["reason"]) || !truth(payload["resume_condition"]) {
		return nil, reject("block_reason", "Reason and resume condition required")
	}
	if task != nil {
		task["before_block"] = task["status"]
		task["status"] = "blocked"
		task["blockers"] = append(array(task["blockers"]), payload)
	} else {
		blocker := mapping{"task_id": nil}
		for key, item := range payload {
			if key != "task_id" {
				blocker[key] = item
			}
		}
		state["status"] = "blocked"
		state["blockers"] = append(array(state["blockers"]), blocker)
	}
	return mapping{"blocked": payload}, nil
}

func extendBudget(state, task, payload mapping) (any, error) {
	budget := str(payload["budget"])
	if task == nil || budget != "review" && budget != "test" || !truth(payload["source"]) || !truth(payload["text"]) {
		return nil, reject("budget_decision", "Explicit user decision and source required")
	}
	field, reason := "review_limit", "review_limit_reached"
	if budget == "test" {
		field, reason = "test_repair_limit", "test_repair_limit_reached"
	}
	limit, valid := integer(payload["limit"])
	if !valid || limit <= intValue(task[field]) || limit >= 1_000_000 {
		return nil, reject("finite_limit", "New limit must be a larger finite integer")
	}
	task[field] = limit
	task["budget_decisions"] = append(array(task["budget_decisions"]), payload)
	blockers := []any{}
	for _, raw := range array(state["blockers"]) {
		blocker := object(raw)
		if blocker["reason"] != reason || blocker["task_id"] != object(task["plan"])["id"] {
			blockers = append(blockers, blocker)
		}
	}
	state["blockers"] = blockers
	state["status"] = "active"
	if len(blockers) > 0 {
		state["status"] = "blocked"
	}
	return mapping{"limit": limit, "status": state["status"]}, nil
}

func blockBudget(state, task mapping, reason string) (any, error) {
	item := mapping{"reason": reason, "task_id": object(task["plan"])["id"], "resume_condition": "Explicit finite user budget extension"}
	state["status"] = "blocked"
	for _, current := range array(state["blockers"]) {
		if digest(current) == digest(item) {
			return mapping{"blocked": reason}, nil
		}
	}
	state["blockers"] = append(array(state["blockers"]), item)
	return mapping{"blocked": reason}, nil
}

func repairTask(state, task, payload mapping) (any, error) {
	for key := range payload {
		switch key {
		case "reason", "defect_evidence", "executor", "paths":
		default:
			return nil, reject("repair_schema", "Repair accepts evidence and executor assignment; independent checks record failures")
		}
	}
	if task == nil || task["status"] == "pending" || !truth(payload["reason"]) {
		return nil, reject("repair_reason", "Repair requires a started task and reason")
	}
	if !truth(task["failure"]) && !truth(payload["defect_evidence"]) {
		return nil, reject("repair_evidence", "Provide reproducible defect evidence")
	}
	if intValue(task["review_rounds_started"]) >= intValue(task["review_limit"]) {
		return blockBudget(state, task, "review_limit_reached")
	}
	if truth(task["last_check_failed"]) {
		if truth(task["active_repair"]) {
			return nil, reject("repair_active", "Resume existing repair cycle")
		}
		cycles := intValue(task["test_repair_cycles_started"])
		if cycles >= intValue(task["test_repair_limit"]) {
			return blockBudget(state, task, "test_repair_limit_reached")
		}
		task["active_repair"] = fmt.Sprintf("cycle-%d", cycles)
	}
	executor := task["executor"]
	if value, exists := payload["executor"]; exists {
		executor = value
	}
	taskID := str(object(task["plan"])["id"])
	role := object(object(state["roles"])[str(executor)])
	if role["kind"] != "executor" || role["task_id"] != taskID || role["status"] != "active" && role["status"] != "finished" {
		return nil, reject("executor_missing", "Use the available assigned author or registered successor")
	}
	role["status"] = "active"
	task["executor"] = role["role_id"]
	if truth(object(task["worktree"])["integrated"]) {
		task["worktree_history"] = append(array(task["worktree_history"]), mapping{"worktree": task["worktree"], "reason": "repair integrated result"})
		task["worktree"], task["integration_active"] = nil, false
		delete(task, "freeze_base")
	}
	task["repairing_result"], task["status"] = true, "repairing"
	affected := map[string]bool{taskID: true}
	tasks := object(state["tasks"])
	for expanded := true; expanded; {
		expanded = false
		for id, value := range tasks {
			if affected[id] {
				continue
			}
			for _, dependency := range stringArray(object(object(value)["plan"])["depends_on"]) {
				if affected[dependency] {
					affected[id], expanded = true, true
				}
			}
		}
	}
	for id := range affected {
		other := object(tasks[id])
		if id != taskID && other["status"] == "accepted" {
			other["before_block"], other["status"] = "accepted", "blocked"
			other["blockers"] = append(array(other["blockers"]), mapping{"reason": "predecessor_changed", "resume_condition": "Reverify dependency"})
		}
	}
	return mapping{"status": "repairing", "cycle": task["active_repair"]}, nil
}

func startTask(state, task mapping, taskID string, payload mapping, directory string) (any, error) {
	if !includes(available(state), taskID) {
		return nil, reject("task_unavailable", "Dependencies or conflicts prevent admission")
	}
	if info, err := os.Stat(filepath.Join(directory, "dashboard.html")); err != nil || !info.Mode().IsRegular() {
		return nil, reject("dashboard_missing", "Generate the initial dashboard before starting")
	}
	if !truth(task["checks"]) {
		return nil, reject("checks_missing", "Register planned and project checks first")
	}
	role := object(object(state["roles"])[str(payload["role_id"])])
	if role["kind"] != "executor" || role["task_id"] != taskID || role["status"] != "active" {
		return nil, reject("executor_missing", "Register a fresh executor")
	}
	paths := array(payload["paths"])
	seen := map[string]bool{}
	for _, raw := range paths {
		name, ok := raw.(string)
		if !ok || name == "." || path.IsAbs(name) || strings.ContainsAny(name, "\\:") || path.Clean(name) != name ||
			name == ".." || strings.HasPrefix(name, "../") {
			return nil, reject("task_paths", "Use canonical project-relative file paths")
		}
		if seen[name] {
			return nil, reject("task_paths", "Explicit owned paths required")
		}
		seen[name] = true
		owned, err := contained(str(object(state["basis"])["project_root"]), name)
		if err != nil {
			return nil, err
		}
		if info, err := os.Stat(owned); err == nil && info.IsDir() {
			return nil, reject("task_paths", "List each owned file; directories obscure mixed ownership")
		}
	}
	if len(paths) == 0 {
		return nil, reject("task_paths", "Explicit owned paths required")
	}
	for id, value := range object(state["tasks"]) {
		other := object(value)
		if id == taskID || other["status"] == "pending" || other["status"] == "accepted" {
			continue
		}
		for name := range seen {
			for _, occupied := range stringArray(other["paths"]) {
				if strings.EqualFold(name, occupied) {
					return nil, reject("shared_files", "Another unfinished task owns one of these files")
				}
			}
		}
	}
	worktree := object(task["worktree"])
	if worktree == nil || truth(worktree["removed"]) {
		return nil, reject("worktree_missing", "Every task needs a registered isolated worktree")
	}
	source, err := snapshot(state, str(worktree["path"]))
	if err != nil {
		return nil, err
	}
	if paths := stringArray(source["dirty_paths"]); len(paths) != 0 {
		return nil, reject("dirty_candidate", "Commit or preserve changes before verification: "+strings.Join(paths, ", "))
	}
	task["status"], task["paths"], task["executor"], task["attempt"], task["start_snapshot"] =
		"running", paths, payload["role_id"], intValue(task["attempt"])+1, source
	return mapping{"status": "running"}, nil
}
