package apply

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func gitTransition(state, task, event mapping, directory string) (any, error) {
	switch event["type"] {
	case "worktree_refresh", "worktree_refresh_resolve":
		return refreshWorktree(state, task, event, directory)
	default:
		return transferWorktree(state, task, event, directory)
	}
}

func transferWorktree(state, task, event mapping, directory string) (any, error) {
	worktree := object(task["worktree"])
	if worktree == nil {
		return nil, reject("worktree_required", "Integration requires a registered worktree task")
	}
	if task["status"] != "integrating" {
		return nil, reject("integration_phase", "Review the task before transfer")
	}
	if err := reviewed(task); err != nil {
		return nil, err
	}
	if _, err := requirePassed(state, task, directory, stageFor(task)); err != nil {
		return nil, err
	}
	root := str(object(state["basis"])["project_root"])
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	if head != state["execution_head"] {
		return nil, reject("execution_reconciliation", "Inspect and reconcile the external HEAD before integration")
	}
	source := str(worktree["path"])
	commit, err := gitText(source, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	if commit != object(task["candidate_commit"])["sha"] {
		return nil, reject("commit_candidate", "Transfer the verified local commit")
	}
	if event["type"] == "transfer" {
		return makeTransfer(state, task, worktree, source, commit, directory)
	}
	return integrateTransfer(state, task, event, worktree, root, head, directory)
}

func makeTransfer(state, task, worktree mapping, source, commit, directory string) (any, error) {
	base := str(worktree["base"])
	changed, err := changedPaths(source, base, "HEAD")
	if err != nil {
		return nil, err
	}
	if len(outside(changed, stringArray(task["paths"]))) != 0 {
		return nil, reject("transfer_ownership", "Changed files outside task ownership require explicit accounting")
	}
	tree, err := gitText(source, "rev-parse", "HEAD^{tree}")
	if err != nil {
		return nil, err
	}
	patch, err := gitBytes(source, "diff", "--binary", "--full-index", base, tree)
	if err != nil {
		return nil, err
	}
	relative := fmt.Sprintf("runs/%s/tasks/%s/%d/transfer.patch",
		state["run_id"], object(task["plan"])["id"], intValue(task["attempt"]))
	path, err := contained(directory, relative)
	if err != nil {
		return nil, err
	}
	if err := atomicWrite(path, patch); err != nil {
		return nil, err
	}
	current, err := snapshot(state, source)
	if err != nil {
		return nil, err
	}
	transfer := mapping{"path": relative, "sha256": digest(patch), "tree": tree, "base": base,
		"commit": commit, "snapshot": current, "paths": task["paths"]}
	task["transfer"] = transfer
	manifest, err := contained(directory, relative+".json")
	if err != nil {
		return nil, err
	}
	return transfer, writeJSON(manifest, transfer)
}

func integrateTransfer(state, task, event, worktree mapping, root, head, directory string) (any, error) {
	transfer := object(task["transfer"])
	if transfer == nil {
		return nil, reject("transfer_missing", "Create an unchanged complete transfer package")
	}
	source, err := snapshot(state, str(worktree["path"]))
	if err != nil {
		return nil, err
	}
	if digest(transfer["snapshot"]) != digest(source) {
		return nil, reject("transfer_missing", "Create an unchanged complete transfer package")
	}
	patchPath, err := contained(directory, str(transfer["path"]))
	if err != nil {
		return nil, err
	}
	patch, err := os.ReadFile(patchPath)
	if err != nil {
		return nil, fileError(err, patchPath)
	}
	if digest(patch) != transfer["sha256"] {
		return nil, reject("transfer_corrupt", "Patch hash mismatch")
	}
	taskID := object(task["plan"])["id"]
	for id, raw := range object(state["tasks"]) {
		if id != taskID && truth(object(raw)["integration_active"]) {
			return nil, reject("integration_busy", "Integrate one task at a time")
		}
	}
	pending, err := pendingEffects(directory, state, "integrate")
	if err != nil {
		return nil, err
	}
	for _, record := range pending {
		if object(object(record["request"])["event"])["event_id"] != event["event_id"] {
			return nil, reject("integration_unresolved", "Recover or resolve the existing integration intent first")
		}
	}
	before, err := snapshot(state, root)
	if err != nil {
		return nil, err
	}
	path, err := effectPath(directory, state, event)
	if err != nil {
		return nil, err
	}
	if !existingFile(path) {
		if err := cleanSource(before); err != nil {
			return nil, err
		}
	}
	journal, err := prepareEffect(directory, state, event, "integrate", mapping{
		"head": head, "before": before, "package": transfer["sha256"],
	})
	if err != nil {
		return nil, err
	}
	expected := journal.precondition()
	head, err = gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	if head != expected["head"] {
		return nil, reject("integration_head", "Execution HEAD changed during integration")
	}
	owned := stringArray(task["paths"])
	if len(outside(stringArray(before["dirty_paths"]), owned)) != 0 {
		return nil, reject("integration_scope", "Preserve changes outside the integration paths")
	}
	if _, exists := journal.record["expected_tree"]; !exists {
		tree, err := previewTransfer(root, head, patchPath, patch)
		if err != nil {
			return nil, err
		}
		journal.record["expected_tree"] = tree
		if err := writeJSON(journal.path, journal.record); err != nil {
			return nil, err
		}
	}
	unchanged := digest(before) == digest(expected["before"])
	expectedTree := journal.record["expected_tree"]
	if expectedTree == nil {
		if !unchanged {
			return nil, reject("integration_drift", "Execution source changed during conflict preview")
		}
		return journal.observe(mapping{"status": "conflict", "before": before, "after": before,
			"head": head, "next": "worktree_refresh"})
	}
	switch {
	case journal.record["phase"] == "observed":
		if digest(before) != digest(object(journal.record["result"])["after"]) {
			return nil, reject("integration_drift", "Observed integration changed")
		}
	case !unchanged:
		if gitCommand(root, nil, "apply", "--reverse", "--check", patchPath).err != nil {
			return nil, reject("integration_ambiguous", "Inspect partial/conflicting transfer; do not replay")
		}
	case len(patch) > 0:
		if err := applyTransfer(root, patchPath); err != nil {
			return nil, err
		}
	}
	after, err := snapshot(state, root)
	if err != nil {
		return nil, err
	}
	tree, err := taskTree(root, head, owned)
	if err != nil {
		return nil, err
	}
	if tree != expectedTree {
		return nil, reject("integration_drift", "Integration differs from the recorded Git merge; preserve and resolve explicitly")
	}
	result, err := journal.observe(mapping{"before": expected["before"], "after": after, "head": after["commit"]})
	if err != nil {
		return nil, err
	}
	worktree["integrated"], worktree["integration_tree"] = true, expectedTree
	task["integration_active"], task["freeze_base"] = true, expected["before"]
	return result, nil
}

// Use a private index so conflict detection leaves the execution index and
// working tree untouched. Git can still store objects produced by its merge.
func previewTransfer(root, base, path string, patch []byte) (any, error) {
	private, err := os.MkdirTemp("", "sdd-apply-index-")
	if err != nil {
		return nil, err
	}
	defer os.RemoveAll(private)
	environment := []string{"GIT_INDEX_FILE=" + filepath.Join(private, "index")}
	if _, err := gitCommand(root, environment, "read-tree", base).checked(); err != nil {
		return nil, err
	}
	if len(patch) > 0 && gitCommand(root, environment, "apply", "--cached", "--3way", path).err != nil {
		return nil, nil
	}
	tree, err := gitCommand(root, environment, "write-tree").checked()
	if err != nil {
		return nil, err
	}
	return strings.TrimSpace(string(tree)), nil
}

func applyTransfer(root, path string) error {
	_, err := gitBytes(root, "apply", "--3way", "--index", path)
	return err
}
