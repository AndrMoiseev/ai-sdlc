package apply

import (
	"errors"
	"os"
	"path/filepath"
)

func refreshWorktree(state, task, event mapping, directory string) (any, error) {
	old := object(task["worktree"])
	if old == nil {
		return nil, reject("worktree_required", "Refresh requires a registered task worktree")
	}
	if task["status"] == "accepted" || truth(old["integrated"]) || truth(old["removed"]) || truth(task["integration_active"]) {
		return nil, reject("refresh_phase", "Refresh unfinished, unintegrated work only")
	}
	roles := object(state["roles"])
	for _, id := range stringArray(task["roles"]) {
		if object(roles[id])["status"] == "active" {
			return nil, reject("writer_active", "Finish or reconcile all task roles before refreshing")
		}
	}
	if truth(task["procedures"]) {
		return nil, reject("procedure_active", "Finish pending procedures")
	}
	basis := object(state["basis"])
	root := str(basis["project_root"])
	if gitBranch(root) != basis["branch"] {
		return nil, reject("branch_changed", "Restore execution branch")
	}
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	if head != state["execution_head"] {
		return nil, reject("execution_reconciliation", "Inspect and reconcile the clean external HEAD before refreshing task work")
	}
	payload := object(event["payload"])
	resolving := event["type"] == "worktree_refresh_resolve"
	original := str(event["event_id"])
	if resolving {
		original = str(payload["intent_id"])
	}
	if original == "" {
		return nil, reject("refresh_intent", "Reference the original refresh event")
	}
	path, err := effectPath(directory, state, mapping{"event_id": original})
	if err != nil {
		return nil, err
	}
	integration, err := pendingEffects(directory, state, "integrate")
	if err != nil {
		return nil, err
	}
	if len(integration) != 0 {
		return nil, reject("integration_unresolved", "Resolve pending integration first")
	}
	taskID := str(object(task["plan"])["id"])
	pending, err := pendingEffects(directory, state, "worktree_refresh")
	if err != nil {
		return nil, err
	}
	for _, record := range pending {
		request := object(record["request"])
		if request["task_id"] == taskID && object(request["event"])["event_id"] != original {
			return nil, reject("refresh_pending", "Recover the original refresh intent")
		}
	}
	if resolving {
		return resolveRefresh(state, task, payload, old, roles, root, path, taskID)
	}
	if !truth(payload["reason"]) || !truth(payload["evidence"]) {
		return nil, reject("refresh_evidence", "Record reason and evidence for refresh")
	}
	var saved mapping
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		saved, err = refreshPrecondition(state, task, event, old, directory, root, head, taskID)
		if err != nil {
			return nil, err
		}
	} else if err != nil {
		return nil, err
	}
	journal, err := prepareEffect(directory, state, event, "worktree_refresh", saved)
	if err != nil {
		return nil, err
	}
	if err := applyRefresh(state, root, journal); err != nil {
		return nil, err
	}
	return finishRefresh(state, task, root, journal, nil)
}

func refreshPrecondition(state, task, event, old mapping, directory, root, head, taskID string) (mapping, error) {
	source := str(old["path"])
	registered, err := registeredWorktree(root, source)
	if err != nil {
		return nil, err
	}
	if registered == nil {
		return nil, reject("unregistered_worktree", "Preserve the registered source worktree")
	}
	status, err := gitStatus(source, nil, true)
	if err != nil {
		return nil, err
	}
	if len(stringArray(status["dirty_paths"])) != 0 || len(stringArray(status["ignored_paths"])) != 0 {
		return nil, reject("unknown_worktree_data", "Commit owned work and preserve unknown files before refresh")
	}
	base := str(old["base"])
	changes, err := changedPaths(source, base, "HEAD")
	if err != nil {
		return nil, err
	}
	if len(outside(changes, stringArray(task["paths"]))) != 0 {
		return nil, reject("unknown_worktree_data", "Source commits exceed task ownership")
	}
	if head == base && truth(object(old["snapshot"])["commit"]) {
		return nil, reject("refresh_unchanged", "Worktree already uses current HEAD")
	}
	run := str(state["run_id"])
	name := taskID + "-" + str(event["event_id"])
	destination, err := contained(str(old["workspace"]), filepath.Join(run, name))
	if err != nil {
		return nil, err
	}
	registered, err = registeredWorktree(root, destination)
	if err != nil {
		return nil, err
	}
	_, statErr := os.Stat(destination)
	if statErr == nil || registered != nil {
		return nil, reject("refresh_destination_exists", "Replacement path must be unused")
	}
	if !errors.Is(statErr, os.ErrNotExist) {
		return nil, statErr
	}
	sourceCommit := str(status["head"])
	patch, err := gitBytes(source, "diff", "--binary", "--full-index", base, sourceCommit)
	if err != nil {
		return nil, err
	}
	patchPath, err := contained(directory, filepath.Join("runs", run, "refresh", str(event["event_id"]), "task.patch"))
	if err != nil {
		return nil, err
	}
	if err := atomicWrite(patchPath, patch); err != nil {
		return nil, err
	}
	return mapping{"old": copyMapping(old), "new": destination, "base": head, "branch": "sdd/" + run + "/" + name,
		"source_commit": sourceCommit, "source_branch": status["branch"], "patch": patchPath, "patch_hash": digest(patch)}, nil
}

func applyRefresh(state mapping, root string, journal *effectJournal) error {
	saved := journal.precondition()
	if _, present := saved["source_commit"]; !present {
		return reject("legacy_refresh", "Preserve old refresh intent and worktrees; reconcile explicitly before retrying")
	}
	if err := refreshSourceUnchanged(saved); err != nil {
		return err
	}
	base, branch, destination := str(saved["base"]), str(saved["branch"]), str(saved["new"])
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	if head != base {
		return reject("refresh_head_changed", "Execution HEAD changed during refresh")
	}
	_, hasBaseline := journal.record["baseline"]
	if _, err := os.Stat(destination); errors.Is(err, os.ErrNotExist) {
		if hasBaseline {
			return reject("refresh_destination_missing", "Replacement disappeared; preserve intent")
		}
		if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
			return err
		}
		if _, err := gitText(root, "worktree", "add", "-b", branch, destination, base); err != nil {
			return err
		}
	} else if err != nil {
		return err
	}
	status, err := refreshDestination(root, destination, base, branch, "Replacement is not registered")
	if err != nil {
		return err
	}
	pristine := len(stringArray(status["dirty_paths"])) == 0 && len(stringArray(status["ignored_paths"])) == 0
	if !hasBaseline {
		if !pristine {
			return reject("refresh_destination_changed", "Replacement must begin clean")
		}
		baseline, err := snapshot(state, destination)
		if err != nil {
			return err
		}
		journal.record["baseline"] = baseline
		if err := writeJSON(journal.path, journal.record); err != nil {
			return err
		}
	}
	patchPath := str(saved["patch"])
	patch, err := os.ReadFile(patchPath)
	if err != nil {
		return fileError(err, patchPath)
	}
	if digest(patch) != saved["patch_hash"] {
		return reject("transfer_corrupt", "Refresh transfer changed")
	}
	if !truth(journal.record["apply_started"]) {
		if !pristine {
			return reject("refresh_destination_changed", "Replacement changed before transfer")
		}
		tree, err := previewTransfer(destination, base, patchPath, patch)
		if err != nil {
			return err
		}
		journal.record["expected_tree"], journal.record["apply_started"] = tree, true
		if err := writeJSON(journal.path, journal.record); err != nil {
			return err
		}
	}
	if pristine && len(patch) > 0 {
		return applyTransfer(destination, patchPath)
	}
	return nil
}

func refreshDestination(root, destination, base, branch, missing string) (mapping, error) {
	registered, err := registeredWorktree(root, destination)
	if err != nil {
		return nil, err
	}
	if registered == nil {
		return nil, reject("unregistered_worktree", missing)
	}
	status, err := gitStatus(destination, nil, true)
	if err != nil {
		return nil, err
	}
	if status["head"] != base || status["branch"] != branch {
		return nil, reject("refresh_destination_changed", "Replacement branch changed")
	}
	return status, nil
}

func refreshSourceUnchanged(saved mapping) error {
	status, err := gitStatus(str(object(saved["old"])["path"]), nil, true)
	if err != nil {
		return err
	}
	if status["head"] != saved["source_commit"] || status["branch"] != saved["source_branch"] ||
		len(stringArray(status["dirty_paths"])) != 0 || len(stringArray(status["ignored_paths"])) != 0 {
		return reject("refresh_source_changed", "Source changed; preserve both worktrees")
	}
	return nil
}

func resolveRefresh(state, task, payload, old, roles mapping, root, path, taskID string) (any, error) {
	if !existingFile(path) || !truth(payload["resolution"]) || !truth(payload["role_id"]) {
		return nil, reject("refresh_resolution", "Supply intent, resolution and resolver role")
	}
	raw, err := readJSON(path)
	if err != nil {
		return nil, err
	}
	record := object(raw)
	request := object(record["request"])
	journal := &effectJournal{path, record}
	if request["operation"] != "worktree_refresh" || request["task_id"] != taskID ||
		digest(journal.precondition()["old"]) != digest(old) || !truth(record["apply_started"]) {
		return nil, reject("refresh_intent", "Expected this task's pending refresh")
	}
	role := object(roles[str(payload["role_id"])])
	if role["kind"] != "executor" || role["task_id"] != taskID || role["status"] != "finished" || !truth(role["trace"]) {
		return nil, reject("resolution_role", "Registered resolver must finish writing")
	}
	return finishRefresh(state, task, root, journal, payload)
}

func finishRefresh(state, task mapping, root string, journal *effectJournal, resolution mapping) (any, error) {
	saved := journal.precondition()
	old := object(saved["old"])
	base, branch, destination := str(saved["base"]), str(saved["branch"]), str(saved["new"])
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	if head != base {
		return nil, reject("refresh_head_changed", "Execution HEAD changed; preserve both trees")
	}
	status, err := refreshDestination(root, destination, base, branch, "Replacement must remain registered")
	if err != nil {
		return nil, err
	}
	conflicts, err := gitText(destination, "ls-files", "--unmerged")
	if err != nil {
		return nil, err
	}
	if conflicts != "" {
		return nil, reject("refresh_conflict", "Resolve the replacement and retain the old worktree")
	}
	owned := stringArray(task["paths"])
	if len(outside(stringArray(status["dirty_paths"]), owned)) != 0 || len(stringArray(status["ignored_paths"])) != 0 {
		return nil, reject("refresh_scope", "Preserve unexpected replacement files")
	}
	tree, err := taskTree(destination, base, owned)
	if err != nil {
		return nil, err
	}
	if resolution == nil && tree != journal.record["expected_tree"] {
		return nil, reject("refresh_destination_changed", "Replacement differs from recorded Git merge")
	}
	if err := refreshSourceUnchanged(saved); err != nil {
		return nil, err
	}
	history := array(task["worktree_history"])
	entry := selectFields(task, "transfer", "baseline_checks", "start_snapshot", "active_review", "active_reviewers")
	entry["worktree"], entry["retained"] = copyMapping(old), old["path"]
	entry["refresh_event"] = object(object(journal.record["request"])["event"])["event_id"]
	task["worktree_history"] = append(history, entry)
	worktree := copyMapping(old)
	worktree["path"], worktree["base"], worktree["branch"] = destination, base, branch
	worktree["snapshot"], worktree["integrated"] = journal.record["baseline"], false
	delete(worktree, "inventory")
	task["worktree"], task["start_snapshot"] = worktree, journal.record["baseline"]
	for _, field := range []string{"transfer", "freeze_base", "active_reviewers", "review_basis", "candidate_commit"} {
		delete(task, field)
	}
	task["active_review"] = nil
	var resultResolution any
	if resolution != nil {
		task["executor"] = resolution["role_id"]
		resultResolution = resolution
	}
	phase := "running"
	if truth(task["active_repair"]) {
		phase = "repairing"
	}
	switch task["status"] {
	case "blocked":
		task["before_block"] = phase
	case "pending":
	default:
		task["status"] = phase
	}
	state["final"] = nil
	return journal.observe(mapping{"worktree": worktree, "retained": old["path"], "tree": tree,
		"resolution": resultResolution, "next": "Freeze a local candidate commit; run checks and review again"})
}
