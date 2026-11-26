package apply

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func commitInfo(root, sha string) (mapping, error) {
	raw, err := gitText(root, "show", "-s", "--format=%T%n%P%n%B", sha)
	if err != nil {
		return nil, err
	}
	fields := strings.SplitN(raw, "\n", 3)
	if len(fields) != 3 {
		return nil, reject("git_failed", "Invalid commit information")
	}
	var parent any
	if ids := strings.Fields(fields[1]); len(ids) != 0 {
		parent = ids[0]
	}
	return mapping{"tree": fields[0], "parent": parent, "message": strings.TrimSpace(fields[2])}, nil
}

func confirmCommit(state, task, commit mapping) error {
	root := str(object(state["basis"])["project_root"])
	actual, err := commitInfo(root, str(commit["sha"]))
	if err != nil {
		return err
	}
	switch {
	case actual["tree"] != commit["tree"]:
		return reject("commit_tree", "Commit tree mismatch")
	case actual["parent"] != commit["parent"]:
		return reject("commit_parent", "Commit parent mismatch")
	case !strings.Contains(str(actual["message"]), str(object(task["plan"])["id"])):
		return reject("commit_task", "TASK-ID missing from commit")
	}
	if gitCommand(root, nil, "merge-base", "--is-ancestor", str(commit["sha"]), "HEAD").err != nil {
		return reject("commit_branch", "Commit is not in execution branch")
	}
	return nil
}

func cleanSource(source mapping) error {
	if !truth(source["commit"]) {
		return reject("legacy_candidate", "Source snapshots require explicit rebaseline in a task worktree; preserve historical evidence")
	}
	if dirty := stringArray(source["dirty_paths"]); len(dirty) != 0 {
		return reject("dirty_candidate", "Commit or preserve changes before verification: "+strings.Join(dirty, ", "))
	}
	return nil
}

func ownPaths(task mapping, root string) ([]string, error) {
	paths := stringArray(task["paths"])
	if len(paths) == 0 {
		return nil, reject("empty_candidate", "No owned paths")
	}
	for _, name := range paths {
		if _, err := contained(root, name); err != nil {
			return nil, err
		}
		if strings.HasPrefix(name, "sdd/changes/") || strings.HasPrefix(name, "sdd/refactoring/") {
			return nil, reject("normative_ownership", "Execution cannot own SDD documents")
		}
	}
	return paths, nil
}

func outside(paths, owned []string) []string {
	result := []string{}
	for _, name := range paths {
		if !includes(owned, name) {
			result = append(result, name)
		}
	}
	sort.Strings(result)
	return result
}

func writerActive(state, task mapping) bool {
	roles := object(state["roles"])
	for _, id := range stringArray(task["roles"]) {
		role := object(roles[id])
		if role["kind"] == "executor" && role["status"] == "active" {
			return true
		}
	}
	return false
}

func candidateEvent(state, task, event mapping, directory string) (any, error) {
	if task == nil {
		return nil, reject("task_required", "Verification requires a task")
	}
	if !includes([]string{"running", "repairing", "integrating"}, str(task["status"])) {
		return nil, reject("candidate_phase", "Candidate requires completed implementation or integration")
	}
	executor := object(object(state["roles"])[str(task["executor"])])
	if executor["status"] != "finished" {
		return nil, reject("writer_active", "Executor must finish writing before freezing")
	}
	if writerActive(state, task) {
		return nil, reject("writer_active", "All task writers must stop before freezing")
	}
	for _, value := range array(task["checks"]) {
		check := object(value)
		if _, pending := object(check["run"])["setup_required"]; pending && !truth(check["setup"]) {
			return nil, reject("setup_pending", "Resolve all planned setup")
		}
	}
	if workKind(object(state["basis"])) == "refactoring" && !truth(task["baseline_checks"]) {
		return nil, reject("baseline_missing", "Capture existing checks before preparing a refactoring result")
	}
	if err := checkRegistryCurrent(state, task); err != nil {
		return nil, err
	}
	result, err := freezeCandidate(state, task, event, directory)
	if err != nil {
		return nil, err
	}
	task["status"] = "verifying"
	if truth(object(task["worktree"])["integrated"]) {
		task["status"] = "committing"
	}
	return mapping{"commit": result}, nil
}

func freezeCandidate(state, task, event mapping, directory string) (mapping, error) {
	root := taskRoot(state, task)
	worktree := object(task["worktree"])
	if worktree == nil || truth(worktree["removed"]) {
		return nil, reject("worktree_missing", "Freeze candidates in a registered task worktree")
	}
	integrated := truth(worktree["integrated"])
	expectedBranch := worktree["branch"]
	if integrated {
		expectedBranch = object(state["basis"])["branch"]
	}
	branch := gitBranch(root)
	if branch == "" || branch != expectedBranch {
		return nil, reject("branch_changed", "Restore the registered candidate branch")
	}
	unmerged, err := gitText(root, "ls-files", "--unmerged")
	if err != nil {
		return nil, err
	}
	if unmerged != "" {
		return nil, reject("unmerged_index", "Resolve conflicts before freezing")
	}
	source, err := snapshot(state, root)
	if err != nil {
		return nil, err
	}
	owned, err := ownPaths(task, root)
	if err != nil {
		return nil, err
	}
	if unexpected := outside(stringArray(source["dirty_paths"]), owned); len(unexpected) != 0 {
		return nil, reject("candidate_scope", "Changes outside task ownership: "+strings.Join(unexpected, ", "))
	}
	baseline := object(task["start_snapshot"])
	if value, exists := task["freeze_base"]; exists {
		baseline = object(value)
	}
	if !truth(baseline["commit"]) {
		return nil, reject("legacy_candidate", "Rebaseline the preserved task before using commit-bound verification")
	}
	changed, err := changedPaths(root, str(baseline["commit"]), "HEAD")
	if err != nil {
		return nil, err
	}
	if len(outside(changed, owned)) != 0 {
		return nil, reject("candidate_scope", "Commits changed files outside task ownership")
	}
	parent := str(source["commit"])
	tree, err := taskTree(root, parent, owned)
	if err != nil {
		return nil, err
	}
	if integrated && tree != worktree["integration_tree"] {
		return nil, reject("integration_drift", "Integrated files changed after transfer or recorded conflict resolution")
	}
	journal, err := prepareEffect(directory, state, event, "candidate_commit", mapping{"root": root, "parent": parent, "tree": tree})
	if err != nil {
		return nil, err
	}
	expected := journal.precondition()
	if integrated && expected["parent"] != state["execution_head"] {
		return nil, reject("execution_reconciliation", "Inspect and reconcile the external HEAD before freezing integrated work")
	}
	marker := "SDD-Candidate: " + str(state["run_id"]) + "/" + str(event["event_id"])
	result := object(journal.record["result"])
	if journal.record["phase"] != "observed" {
		matches, err := findCommits(root, marker)
		if err != nil {
			return nil, err
		}
		sha := parent
		switch {
		case len(matches) > 1:
			return nil, reject("commit_ambiguous", "Multiple commits for one candidate intent")
		case len(matches) == 1:
			sha = matches[0]
		default:
			if parent != expected["parent"] || tree != expected["tree"] {
				return nil, reject("commit_drift", "Candidate intent no longer matches its inputs")
			}
			priorTree, err := gitText(root, "rev-parse", parent+"^{tree}")
			if err != nil {
				return nil, err
			}
			if priorTree != tree || truth(task["repairing_result"]) {
				sha, err = commitTree(root, tree, fmt.Sprintf("%s: candidate\n\n%s", object(task["plan"])["id"], marker))
				if err != nil {
					return nil, err
				}
			}
		}
		result = mapping{"sha": sha, "parent": expected["parent"], "tree": expected["tree"], "root": root, "operation": marker}
		if len(matches) == 0 && sha == parent {
			actual, err := commitInfo(root, sha)
			if err != nil {
				return nil, err
			}
			if truth(actual["parent"]) && strings.Contains(str(actual["message"]), str(object(task["plan"])["id"])) {
				changed, err := changedPaths(root, str(actual["parent"]), sha)
				if err != nil {
					return nil, err
				}
				if len(outside(changed, owned)) == 0 {
					result["parent"] = actual["parent"]
				}
			}
		}
	}
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	actual, err := commitInfo(root, str(result["sha"]))
	if err != nil {
		return nil, err
	}
	if head != result["sha"] || actual["tree"] != result["tree"] {
		return nil, reject("commit_drift", "Candidate commit changed")
	}
	if integrated && result["tree"] != worktree["integration_tree"] {
		return nil, reject("integration_drift", "Commit differs from the recorded integration")
	}
	if result["sha"] != result["parent"] && actual["parent"] != result["parent"] {
		return nil, reject("commit_parent", "Candidate parent changed")
	}
	if _, err := gitBytes(root, append([]string{"reset", "--quiet", head, "--"}, owned...)...); err != nil {
		return nil, err
	}
	after, err := snapshot(state, root)
	if err != nil {
		return nil, err
	}
	if err := cleanSource(after); err != nil {
		return nil, err
	}
	if _, err := journal.observe(result); err != nil {
		return nil, err
	}
	task["candidate_commit"] = result
	return result, nil
}

func gitBranch(root string) string {
	return strings.TrimSpace(string(gitCommand(root, nil, "symbolic-ref", "--quiet", "--short", "HEAD").stdout))
}

func findCommits(root, marker string) ([]string, error) {
	raw, err := gitText(root, "log", "--format=%H%x00%B%x00", "--fixed-strings", "--grep", marker)
	if err != nil {
		return nil, err
	}
	records, matches := strings.Split(raw, "\x00"), []string{}
	for i := 0; i+1 < len(records); i += 2 {
		if includes(strings.Split(records[i+1], "\n"), marker) {
			matches = append(matches, strings.TrimSpace(records[i]))
		}
	}
	return matches, nil
}

func commitTree(root, tree, message string) (string, error) {
	dir, err := os.MkdirTemp("", "sdd-apply-index-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(dir)
	environment := []string{"GIT_INDEX_FILE=" + filepath.Join(dir, "index")}
	if _, err := gitCommand(root, environment, "read-tree", tree).checked(); err != nil {
		return "", err
	}
	if _, err := gitCommand(root, environment, "commit", "--allow-empty", "-m", message).checked(); err != nil {
		return "", err
	}
	return gitText(root, "rev-parse", "HEAD")
}

func verifiedTransfer(state, task mapping, directory string) ([]any, error) {
	worktree := object(task["worktree"])
	transfer := object(task["transfer"])
	if transfer == nil || !truth(worktree["integration_tree"]) {
		return nil, reject("transfer_missing", "Integrate the verified transfer package first")
	}
	source, err := snapshot(state, str(worktree["path"]))
	if err != nil {
		return nil, err
	}
	if digest(transfer["snapshot"]) != digest(source) {
		return nil, reject("transfer_changed", "The verified worktree changed after transfer")
	}
	sourceTask := copyMapping(task)
	worktree = copyMapping(worktree)
	worktree["integrated"] = false
	sourceTask["worktree"] = worktree
	return requirePassed(state, sourceTask, directory, "independent")
}

func commitEvent(state, task, event mapping, directory string) (any, error) {
	if task == nil || task["status"] != "committing" {
		return nil, reject("commit_phase", "Only reviewed candidates may be committed")
	}
	if err := reviewed(task); err != nil {
		return nil, err
	}
	if _, err := verifiedTransfer(state, task, directory); err != nil {
		return nil, err
	}
	if _, err := currentTaskSource(state, task); err != nil {
		return nil, err
	}
	basis := object(state["basis"])
	root := str(basis["project_root"])
	if gitBranch(root) != basis["branch"] {
		return nil, reject("branch_changed", "Execution branch changed")
	}
	head, err := gitText(root, "rev-parse", "HEAD")
	if err != nil {
		return nil, err
	}
	candidate := object(task["candidate_commit"])
	worktree := object(task["worktree"])
	if candidate["sha"] != head || candidate["tree"] != worktree["integration_tree"] {
		return nil, reject("commit_candidate", "Confirm the unchanged recorded integration commit")
	}
	commits := array(task["commits"])
	if event["type"] == "accept" {
		if len(commits) == 0 || object(commits[len(commits)-1])["sha"] != candidate["sha"] {
			return nil, reject("commit_required", "Confirmation of the current integration commit is mandatory")
		}
		confirmed := object(commits[len(commits)-1])
		if err := confirmCommit(state, task, confirmed); err != nil {
			return nil, err
		}
		if workKind(basis) == "refactoring" {
			registry := object(task["check_registry"])
			registry["confirmed_revision"], registry["confirmation_event"] = registry["revision"], event["event_id"]
		}
		task["status"], task["integration_active"] = "accepted", false
		delete(task, "repairing_result")
		return mapping{"status": "accepted", "sha": confirmed["sha"]}, nil
	}
	if !truth(worktree["integrated"]) {
		return nil, reject("integration_required", "Integrate the verified worktree before accepting the task")
	}
	if candidate["root"] != root || candidate["sha"] != head {
		return nil, reject("commit_candidate", "Integration candidate must name execution HEAD")
	}
	if candidate["sha"] == candidate["parent"] {
		return nil, reject("empty_commit", "Task has no changes to commit")
	}
	if err := confirmCommit(state, task, candidate); err != nil {
		return nil, err
	}
	for _, commit := range commits {
		if object(commit)["sha"] == candidate["sha"] {
			return candidate, nil
		}
	}
	task["commits"] = append(commits, candidate)
	return candidate, nil
}
