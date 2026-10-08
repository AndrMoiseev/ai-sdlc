"""Complete binary transfer packages and serialized integration."""
from pathlib import Path
import json
from .common import atomic, contained, digest, git, require, write_json
from .commits import index_tree, reviewed
from .effects import intent, observed
from .state import snapshot
from .verification import current, valid_evidence


def transition(state, task, event, directory):
    require(task and task["worktree"] and state["mode"] == "parallel", "parallel_required", "Integration requires an authorized worktree task")
    require(task["status"] == "integrating", "integration_phase", "Review the task before transfer")
    current(state, task)
    reviewed(task)
    valid_evidence(state, task, directory)
    root = state["basis"]["project_root"]
    worktree = task["worktree"]
    require(git(worktree["path"], "rev-parse", "HEAD") == worktree["base"], "executor_commit", "Executor must leave uncommitted changes")
    if event["type"] == "integration_resolve":
        p = event["payload"]
        require(p.get("intent_id") and p.get("resolution") and p.get("role_id"), "resolution_evidence", "Reference the failed integration and actual resolver result")
        effect = contained(directory, f"runs/{state['run_id']}/effects/{p['intent_id']}.json")
        journal = json.loads(effect.read_text())
        require(journal["request"]["operation"] == "integrate" and journal["request"]["task_id"] == task["plan"]["id"] and journal["phase"] == "prepared", "resolution_intent", "Unresolved integration intent required")
        role = state["roles"].get(p["role_id"])
        require(role and role["task_id"] == task["plan"]["id"] and role["kind"] == "executor" and role["status"] == "finished" and role.get("trace"), "resolution_role", "A registered resolver must finish writing and return its host trace")
        require(not git(root, "ls-files", "--unmerged"), "unresolved_conflicts", "Resolve and stage conflicted task paths first")
        require(git(root, "rev-parse", "HEAD") == journal["request"]["precondition"]["head"], "integration_head", "Execution HEAD changed during conflict resolution")
        observed(effect, journal, {"before": journal["request"]["precondition"]["before"], "after": snapshot(state, root), "resolution": p, "head": git(root, "rev-parse", "HEAD")})
        worktree["integrated"] = True
        task["integration_active"] = True
        task["freeze_base"] = journal["request"]["precondition"]["before"]
        task["executor"] = p["role_id"]
        task["candidate"] = None
        return {"resolved": p["intent_id"], "next": "candidate; independent integration checks and review"}
    if event["type"] == "transfer":
        from .worktrees import inventory
        files = inventory(worktree["path"])
        before_files = worktree["inventory"]
        changed = {p for p in set(files) | set(before_files) if files.get(p) != before_files.get(p)}
        require(changed <= set(task["paths"]), "transfer_ownership", "Changed files outside task ownership require explicit accounting")
        tree = index_tree(worktree["path"], task["paths"], worktree["base"])
        patch = git(worktree["path"], "diff", "--binary", "--full-index", worktree["base"], tree, raw=True)
        relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/transfer.patch"
        atomic(contained(directory, relative), patch)
        task["transfer"] = {"path": relative, "sha256": digest(patch), "tree": tree, "base": worktree["base"], "snapshot": snapshot(state, worktree["path"]), "paths": task["paths"], "inventory": files}
        write_json(contained(directory, relative + ".json"), task["transfer"])
        return task["transfer"]
    package = task.get("transfer")
    require(package and package["snapshot"] == snapshot(state, worktree["path"]), "transfer_missing", "Create an unchanged complete transfer package")
    patch = contained(directory, package["path"])
    require(digest(patch.read_bytes()) == package["sha256"], "transfer_corrupt", "Patch hash mismatch")
    require(not any(t is not task and t.get("integration_active") for t in state["tasks"].values()), "integration_busy", "Integrate one task at a time")
    for pending in (Path(directory) / "runs" / state["run_id"] / "effects").glob("*.json"):
        record = json.loads(pending.read_text())
        require(not (record["phase"] == "prepared" and record["request"]["operation"] == "integrate" and record["request"]["event"]["event_id"] != event["event_id"]), "integration_unresolved", "Recover or resolve the existing integration intent first")
    before = snapshot(state, root)
    effect, journal = intent(directory, state, event, "integrate", {"head": git(root, "rev-parse", "HEAD"), "before": before, "package": package["sha256"]})
    expected = journal["request"]["precondition"]
    if journal["phase"] == "observed":
        require(before == journal["result"]["after"], "integration_drift", "Observed integration changed")
    elif before != expected["before"]:
        # A crash after Git apply can be proved by reverse applicability. An
        # ambiguous or partially conflicted result remains available for repair.
        import subprocess
        result = subprocess.run(["git", "-C", root, "apply", "--reverse", "--check", str(patch)], capture_output=True)
        require(result.returncode == 0, "integration_ambiguous", "Inspect partial/conflicting transfer; do not replay")
    else:
        git(root, "apply", "--3way", "--index", str(patch))
    after = snapshot(state, root)
    result = observed(effect, journal, {"before": expected["before"], "after": after, "head": git(root, "rev-parse", "HEAD")})
    worktree["integrated"] = True
    task["candidate"] = None
    task["integration_active"] = True
    task["freeze_base"] = expected["before"]
    # New candidate and independent integration checks/review are mandatory,
    # including clean application to a changed execution branch.
    return result
