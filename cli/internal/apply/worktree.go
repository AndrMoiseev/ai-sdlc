package apply

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
)

func transitionWorktree(state, task, event mapping, directory string) (any, error) {
	if task == nil {
		return nil, reject("task_required", "Task required")
	}
	if event["type"] == "worktree_create" {
		return createWorktree(state, task, event, directory)
	}
	return removeWorktree(state, task, event, directory)
}

func createWorktree(state, task, event mapping, directory string) (any, error) {
	status, err := executionSource(state)
	if err != nil {
		return nil, err
	}
	if truth(status["dirty_paths"]) || status["head"] != state["execution_head"] {
		return nil, reject("execution_reconciliation", "Resume and reconcile the main tree before starting new task work")
	}
	taskID := str(object(task["plan"])["id"])
	repairing := task["status"] == "repairing" && !truth(task["worktree"])
	if !includes(available(state), taskID) && !repairing || truth(task["worktree"]) {
		return nil, reject("worktree_admission", "Task is not available")
	}
	payload := object(event["payload"])
	workspaceName, err := fieldString(payload, "workspace")
	if err != nil {
		return nil, err
	}
	workspace, err := resolvePath(workspaceName)
	if err != nil {
		return nil, err
	}
	resources := []any{}
	if value, exists := payload["resources"]; exists {
		resources = array(value)
		if resources == nil {
			return nil, reject("resource_schema", "Use explicit resource names")
		}
	}
	for _, resource := range resources {
		if str(resource) == "" {
			return nil, reject("resource_schema", "Use explicit resource names")
		}
	}
	for id, value := range object(state["tasks"]) {
		other := object(value)
		if id != taskID && other["status"] != "accepted" && ownedIntersection(stringArray(resources), stringArray(object(other["worktree"])["resources"]), false) {
			return nil, reject("shared_resources", "Allocate separate ports/databases/temp resources or serialize")
		}
	}
	for _, part := range strings.Split(filepath.ToSlash(workspace), "/") {
		if includes([]string{"skills", ".agents", ".claude"}, part) {
			return nil, reject("runtime_path", "Worktrees belong outside skill collections")
		}
	}
	suffix := ""
	if repairing {
		suffix = "-" + str(event["event_id"])
	}
	path, err := contained(workspace, filepath.Join(str(state["run_id"]), taskID+suffix))
	if err != nil {
		return nil, err
	}
	root := str(object(state["basis"])["project_root"])
	base, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	branch := "sdd/" + str(state["run_id"]) + "/" + taskID + suffix
	journal, err := prepareEffect(directory, state, event, "worktree_create", mapping{"path": path, "base": base, "branch": branch})
	if err != nil {
		return nil, err
	}
	expected := journal.precondition()
	if expected["path"] != path {
		return nil, reject("worktree_path", "Intent path mismatch")
	}
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, err
		}
		if _, err := gitText(root, "worktree", "add", "-b", str(expected["branch"]), path, str(expected["base"])); err != nil {
			return nil, err
		}
	} else if err != nil {
		return nil, err
	}
	registered, err := registeredWorktree(root, path)
	if err != nil {
		return nil, err
	}
	if registered == nil {
		return nil, reject("unregistered_worktree", "Existing path is not this repository's worktree")
	}
	if registered["head"] != expected["base"] || registered["branch"] != expected["branch"] {
		return nil, reject("worktree_changed", "Expected registered task branch at original HEAD")
	}
	current, err := snapshot(state, path)
	if err != nil {
		return nil, err
	}
	worktree := mapping{"path": path, "workspace": workspace, "base": expected["base"], "branch": expected["branch"],
		"integrated": false, "resources": resources, "snapshot": current}
	task["worktree"] = worktree
	if repairing {
		task["start_snapshot"] = current
	}
	return journal.observe(worktree)
}

func removeWorktree(state, task, event mapping, directory string) (any, error) {
	worktree := object(task["worktree"])
	commits := array(task["commits"])
	if worktree == nil || task["status"] != "accepted" || len(commits) == 0 {
		return nil, reject("worktree_unaccepted", "Preserve unaccepted work")
	}
	commit := object(commits[len(commits)-1])
	if err := confirmCommit(state, task, commit); err != nil {
		return nil, err
	}
	root := str(object(state["basis"])["project_root"])
	path := str(worktree["path"])
	intent, err := effectPath(directory, state, event)
	if err != nil {
		return nil, err
	}
	if _, statErr := os.Stat(path); existingFile(intent) && errors.Is(statErr, os.ErrNotExist) {
		journal, err := prepareEffect(directory, state, event, "worktree_remove", mapping{})
		if err != nil {
			return nil, err
		}
		registered, err := registeredWorktree(root, path)
		if err != nil {
			return nil, err
		}
		if registered != nil {
			return nil, reject("worktree_remove_ambiguous", "Git still registers the missing worktree")
		}
		worktree["removed"] = true
		return journal.observe(mapping{"removed": path})
	}
	for _, role := range stringArray(task["roles"]) {
		if object(object(state["roles"])[role])["status"] == "active" {
			return nil, reject("writer_active", "All task roles must have stopped")
		}
	}
	transfer := object(task["transfer"])
	if transfer == nil {
		return nil, reject("unknown_worktree_data", "Preserve unknown or changed files")
	}
	current, err := snapshot(state, path)
	if err != nil {
		return nil, err
	}
	if digest(transfer["snapshot"]) != digest(current) {
		return nil, reject("unknown_worktree_data", "Preserve unknown or changed files")
	}
	actual, err := gitStatus(path, nil, true)
	if err != nil {
		return nil, err
	}
	if truth(actual["dirty_paths"]) || truth(actual["ignored_paths"]) {
		return nil, reject("unknown_worktree_data", "Preserve changed, untracked or ignored worktree data")
	}
	changed, err := changedPaths(path, str(worktree["base"]), "HEAD")
	if err != nil {
		return nil, err
	}
	for _, name := range changed {
		if !includes(stringArray(task["paths"]), name) {
			return nil, reject("unknown_worktree_data", "Preserve commits outside task ownership")
		}
	}
	expected, err := contained(str(worktree["workspace"]), path)
	if err != nil {
		return nil, err
	}
	if expected != path {
		return nil, reject("worktree_escape", "Unregistered path")
	}
	journal, err := prepareEffect(directory, state, event, "worktree_remove", mapping{"path": path, "head": actual["head"], "sha": commit["sha"]})
	if err != nil {
		return nil, err
	}
	if journal.record["phase"] != "prepared" {
		return nil, reject("worktree_recreated", "Preserve data at a previously removed path")
	}
	if _, err := gitText(root, "worktree", "remove", path); err != nil {
		return nil, err
	}
	worktree["removed"] = true
	return journal.observe(mapping{"removed": path})
}
