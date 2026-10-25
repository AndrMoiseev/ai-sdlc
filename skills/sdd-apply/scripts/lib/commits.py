"""Task-only commits using a separate index, with durable crash recovery."""
from .common import contained, require
from .repository import repository
from .effects import intent, observed
from .verification import valid_evidence
from .candidates import same


def freeze(state, task, event, directory):
    """Create a recoverable local commit before testing its immutable identity."""
    from .verification import root_for
    from .state import snapshot, clean_source
    root = root_for(state, task)
    repo = repository(root)
    worktree = task.get("worktree")
    require(worktree and not worktree.get("removed"), "worktree_missing", "Freeze candidates in a registered task worktree")
    expected_branch = state["basis"]["branch"] if worktree.get("integrated") else worktree.get("branch")
    require(expected_branch and repo.branch() == expected_branch, "branch_changed", "Restore the registered candidate branch")
    require(not repo.has_conflicts(), "unmerged_index", "Resolve conflicts before freezing")
    source = snapshot(state, root)
    own_paths(state, task, root)
    require(set(source["dirty_paths"]) <= set(task["paths"]), "candidate_scope",
            "Changes outside task ownership: " + ", ".join(sorted(set(source["dirty_paths"]) - set(task["paths"]))))
    baseline = task.get("freeze_base", task["start_snapshot"])
    require(baseline.get("commit"), "legacy_candidate", "Rebaseline the preserved task before using commit-bound verification")
    require(repo.changed_paths(baseline["commit"]) <= set(task["paths"]), "candidate_scope", "Commits changed files outside task ownership")
    parent = repo.head()
    tree = repo.tree_for_paths(task["paths"], parent)
    path, journal = intent(directory, state, event, "candidate_commit", {"root": root, "parent": parent, "tree": tree})
    expected = journal["request"]["precondition"]
    marker = f"SDD-Candidate: {state['run_id']}/{event['event_id']}"
    matches = repo.find_commits(marker)
    if journal["phase"] == "observed":
        result = journal["result"]
    elif matches:
        require(len(matches) == 1, "commit_ambiguous", "Multiple commits for one candidate intent")
        result = {"sha": matches[0], "parent": expected["parent"], "tree": expected["tree"], "root": root, "operation": marker}
    else:
        require(parent == expected["parent"] and tree == expected["tree"], "commit_drift", "Candidate intent no longer matches its inputs")
        reuse = tree == repo.tree(parent) and not task.get("repairing_result")
        sha = parent if reuse else repo.commit_tree(tree, f"{task['plan']['id']}: candidate\n\n{marker}")
        result = {"sha": sha, "parent": expected["parent"], "tree": expected["tree"], "root": root, "operation": marker}
        if sha == parent:
            actual = repo.commit_info(sha)
            if actual["parent"] and task["plan"]["id"] in actual["message"] and repo.changed_paths(actual["parent"], sha) <= set(task["paths"]):
                result["parent"] = actual["parent"]
    require(repo.head() == result["sha"] and repo.tree(result["sha"]) == result["tree"], "commit_drift", "Candidate commit changed")
    if result["sha"] != result["parent"]:
        actual = repo.commit_info(result["sha"])
        require(actual["parent"] == result["parent"], "commit_parent", "Candidate parent changed")
    # A hook can alter working bytes or the temporary index. Its commit stays
    # available for repair, but cannot acquire passing evidence.
    repo.reset_paths(result["sha"], task["paths"])
    source = snapshot(state, root)
    clean_source(source)
    observed(path, journal, result)
    task["candidate_commit"] = result
    # The caller immediately binds this checked post-hook source to the
    # candidate; no command or working-file mutation occurs between them.
    return source


def reviewed(state, task):
    require(task["reviews"] and same(state, task["reviews"][-1]["candidate"], task["candidate"]) and task["reviews"][-1]["verdict"] == "pass", "review_missing", "Current independent passing review required")


def index_tree(root, paths, base):
    return repository(root).tree_for_paths(paths, base)


def own_paths(state, task, root):
    require(task["paths"], "empty_candidate", "No owned paths")
    for name in task["paths"]:
        contained(root, name)
        require(name not in state["basis"].get("dirty_paths", []), "ownership_overlap", f"Pre-existing index or working changes in {name}")
        require(not name.startswith(("sdd/changes/", "sdd/refactoring/")), "normative_ownership", "Execution cannot own SDD documents")
        require("dirty_paths" in state["basis"], "ownership_unknown", "Legacy basis lacks a path inventory; explicitly rebaseline before committing")


def confirm(state, task, commit):
    root = state["basis"]["project_root"]
    actual = repository(root).commit_info(commit["sha"])
    require(actual["tree"] == commit["tree"], "commit_tree", "Commit tree mismatch")
    require(actual["parent"] == commit["parent"], "commit_parent", "Commit parent mismatch")
    require(task["plan"]["id"] in actual["message"], "commit_task", "TASK-ID missing from commit")
    require(actual["reachable"], "commit_branch", "Commit is not in execution branch")


def transition(state, task, event, directory):
    require(task and task["status"] == "committing", "commit_phase", "Only reviewed candidates may be committed")
    reviewed(state, task)
    valid_evidence(state, task, directory, "integration" if task["worktree"] and task["worktree"].get("integrated") else None)
    root = state["basis"]["project_root"]
    repo = repository(root)
    require(repo.branch() == state["basis"]["branch"], "branch_changed", "Execution branch changed")
    if event["type"] == "accept":
        require(task["commits"], "commit_required", "A commit is mandatory")
        confirm(state, task, task["commits"][-1])
        require(same(state, task["commits"][-1]["candidate"], task["candidate"]), "commit_candidate", "Commit did not record this candidate")
        from .check_registry import confirm as confirm_registry
        confirm_registry(state, task, event)
        task["status"] = "accepted"
        task["integration_active"] = False
        task.pop("repairing_result", None)
        return {"status": "accepted", "sha": task["commits"][-1]["sha"]}
    require(task["worktree"] and task["worktree"].get("integrated"), "integration_required", "Check and review integration before accepting the task")
    result = {**task["candidate_commit"], "candidate": task["candidate"]}
    require(result["root"] == root and result["sha"] == repo.head(), "commit_candidate", "Integration candidate must name execution HEAD")
    require(result["sha"] != result["parent"], "empty_commit", "Task has no changes to commit")
    confirm(state, task, result)
    if not any(c["sha"] == result["sha"] and same(state, c["candidate"], result["candidate"]) for c in task["commits"]):
        task["commits"].append(result)
    return result
