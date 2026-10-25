"""Task-only commits using a separate index, with durable crash recovery."""
from .common import contained, digest, require
from .repository import repository
from .effects import intent, observed
from .verification import current, valid_evidence, candidate
from .candidates import same


def reviewed(state, task):
    require(task["reviews"] and same(state, task["reviews"][-1]["candidate"], task["candidate"]) and task["reviews"][-1]["verdict"] == "pass", "review_missing", "Current independent passing review required")


def index_tree(root, paths, base):
    return repository(root).tree_for_paths(paths, base)


def own_paths(state, task, root):
    require(task["paths"], "empty_candidate", "No owned paths")
    for name in task["paths"]:
        contained(root, name)
        require(name not in state["basis"].get("dirty_paths", []), "ownership_overlap", f"Pre-existing index or working changes in {name}")
        require(not name.startswith("sdd/changes/"), "normative_ownership", "Execution cannot own SDD documents")
        initial = state["baseline"]["files"].get(name)
        # Conservatively block mixed ownership within a file rather than commit
        # another person's hunk. Explicit separation is needed before resuming.
        if "dirty_paths" not in state["basis"]:
            require(not state["basis"].get("index_patch"), "ownership_unknown", "Older basis has staged changes without a path inventory; reconcile ownership first")
            head_bytes = repository(root).content(state['basis']['head'], name, filtered=True)
            raw_bytes = repository(root).content(state['basis']['head'], name)
            require(initial is None or initial["sha256"] in {digest(head_bytes), digest(raw_bytes)}, "ownership_overlap", f"Pre-existing changes in {name}; separate ownership")


def confirm(state, task, commit):
    root = state["basis"]["project_root"]
    actual = repository(root).commit_info(commit["sha"])
    require(actual["tree"] == commit["tree"], "commit_tree", "Commit tree mismatch")
    require(actual["parent"] == commit["parent"], "commit_parent", "Commit parent mismatch")
    require(task["plan"]["id"] in actual["message"], "commit_task", "TASK-ID missing from commit")
    require(actual["reachable"], "commit_branch", "Commit is not in execution branch")


def transition(state, task, event, directory):
    require(task and task["status"] == "committing", "commit_phase", "Only reviewed candidates may be committed")
    current(state, task)
    reviewed(state, task)
    valid_evidence(state, task, directory, "integration" if task["worktree"] and task["worktree"].get("integrated") else None)
    root = state["basis"]["project_root"]
    repo = repository(root)
    require(repo.branch() == state["basis"]["branch"], "branch_changed", "Execution branch changed")
    if event["type"] == "accept":
        require(task["commits"], "commit_required", "A commit is mandatory")
        confirm(state, task, task["commits"][-1])
        require(same(state, task["commits"][-1]["candidate"], task["candidate"]), "commit_candidate", "Commit did not record this candidate")
        task["status"] = "accepted"
        task["integration_active"] = False
        return {"status": "accepted", "sha": task["commits"][-1]["sha"]}
    own_paths(state, task, root)
    parent = repo.head()
    tree = index_tree(root, task["paths"], parent)
    path, journal = intent(directory, state, event, "commit", {"parent": parent, "tree": tree, "candidate": task["candidate"]})
    expected = journal["request"]["precondition"]
    marker = f"SDD-Operation: {state['run_id']}/{event['event_id']}"
    matches = repo.find_commits(marker)
    if journal["phase"] == "observed":
        result = journal["result"]
        confirm(state, task, result)
    elif matches:
        require(len(matches) == 1, "commit_ambiguous", "Multiple commits for one intent")
        result = {"sha": matches[0], "parent": expected["parent"], "tree": expected["tree"], "candidate": expected["candidate"], "operation": marker}
        confirm(state, task, result)
        observed(path, journal, result)
    else:
        require(parent == expected["parent"] and tree == expected["tree"], "commit_drift", "Commit intent no longer matches HEAD or candidate")
        require(tree != repo.tree("HEAD"), "empty_commit", "Task has no changes to commit")
        sha = repo.commit_tree(tree, f"{task['plan']['id']}: implement verified result\n\n{marker}")
        result = {"sha": sha, "parent": parent, "tree": tree, "candidate": task["candidate"], "operation": marker}
        # Hooks may change files or the temporary index. Keep the resulting
        # commit, but refuse acceptance and recover from the recorded intent.
        confirm(state, task, result)
        current(state, task)
        observed(path, journal, result)
    # Refresh only task entries in the real index; unrelated staged entries stay.
    repo.reset_paths(result["sha"], task["paths"])
    if result["sha"] not in {c["sha"] for c in task["commits"]}:
        task["commits"].append(result)
    return result
