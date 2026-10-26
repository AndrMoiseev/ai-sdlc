"""Complete binary transfer packages and serialized integration."""
from .repository import repository
from pathlib import Path
import json
from .common import digest, require, write_json
from . import artifact_storage as artifacts
from .artifact_storage import write as atomic
from .commits import index_tree, reviewed
from .effects import intent, observed
from .state import snapshot, clean_source
from .verification import valid_evidence


def transition(state, task, event, directory):
    require(task and task["worktree"], "worktree_required", "Integration requires a registered worktree task")
    require(task["status"] == "integrating", "integration_phase", "Review the task before transfer")
    reviewed(state, task)
    valid_evidence(state, task, directory)
    root = state["basis"]["project_root"]
    worktree = task["worktree"]
    source_repo = repository(worktree["path"])
    require(source_repo.head() == task["candidate_commit"]["sha"], "commit_candidate", "Transfer the verified local commit")
    if event["type"] == "integration_resolve":
        p = event["payload"]
        require(p.get("intent_id") and p.get("resolution") and p.get("role_id"), "resolution_evidence", "Reference the failed integration and actual resolver result")
        effect = artifacts.contained(directory, f"runs/{state['run_id']}/effects/{p['intent_id']}.json")
        journal = json.loads(artifacts.read_text(effect))
        require(journal["request"]["operation"] == "integrate" and journal["request"]["task_id"] == task["plan"]["id"] and journal["phase"] == "prepared", "resolution_intent", "Unresolved integration intent required")
        role = state["roles"].get(p["role_id"])
        require(role and role["task_id"] == task["plan"]["id"] and role["kind"] == "executor" and role["status"] == "finished" and role.get("trace"), "resolution_role", "A registered resolver must finish writing and return its host trace")
        require(not repository(root).has_conflicts(), "unresolved_conflicts", "Resolve and stage conflicted task paths first")
        require(repository(root).head() == journal["request"]["precondition"]["head"], "integration_head", "Execution HEAD changed during conflict resolution")
        observed(effect, journal, {"before": journal["request"]["precondition"]["before"], "after": snapshot(state, root), "resolution": p, "head": repository(root).head()})
        worktree["integrated"] = True
        task["integration_active"] = True
        task["freeze_base"] = journal["request"]["precondition"]["before"]
        task["executor"] = p["role_id"]
        task["candidate"] = None
        return {"resolved": p["intent_id"], "next": "candidate; independent integration checks and review"}
    if event["type"] == "transfer":
        changed = source_repo.changed_paths(worktree["base"])
        require(changed <= set(task["paths"]), "transfer_ownership", "Changed files outside task ownership require explicit accounting")
        tree = source_repo.tree("HEAD")
        patch = source_repo.diff_trees(worktree["base"], tree)
        relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/transfer.patch"
        atomic(artifacts.contained(directory, relative), patch)
        task["transfer"] = {"path": relative, "sha256": digest(patch), "tree": tree, "base": worktree["base"], "commit": source_repo.head(), "snapshot": snapshot(state, worktree["path"]), "paths": task["paths"]}
        write_json(artifacts.contained(directory, relative + ".json"), task["transfer"])
        return task["transfer"]
    package = task.get("transfer")
    require(package and package["snapshot"] == snapshot(state, worktree["path"]), "transfer_missing", "Create an unchanged complete transfer package")
    patch = artifacts.contained(directory, package["path"])
    require(digest(artifacts.read_bytes(patch)) == package["sha256"], "transfer_corrupt", "Patch hash mismatch")
    require(not any(t is not task and t.get("integration_active") for t in state["tasks"].values()), "integration_busy", "Integrate one task at a time")
    for pending in artifacts.paths(Path(directory) / "runs" / state["run_id"] / "effects", "*.json"):
        record = json.loads(artifacts.read_text(pending))
        require(not (record["phase"] == "prepared" and record["request"]["operation"] == "integrate" and record["request"]["event"]["event_id"] != event["event_id"]), "integration_unresolved", "Recover or resolve the existing integration intent first")
    before = snapshot(state, root)
    effect_path = artifacts.contained(directory, f"runs/{state['run_id']}/effects/{event['event_id']}.json")
    if not artifacts.exists(effect_path):
        clean_source(before)
    effect, journal = intent(directory, state, event, "integrate", {"head": repository(root).head(), "before": before, "package": package["sha256"]})
    expected = journal["request"]["precondition"]
    require(repository(root).head() == expected["head"], "integration_head", "Execution HEAD changed during integration")
    require(set(before["dirty_paths"]) <= set(task["paths"]), "integration_scope", "Preserve changes outside the integration paths")
    if "expected_tree" not in journal:
        journal["expected_tree"] = repository(root).preview_patch(expected["head"], patch)
        write_json(effect, journal)
    if journal["phase"] == "observed":
        require(before == journal["result"]["after"], "integration_drift", "Observed integration changed")
    elif before != expected["before"]:
        # A crash after Git apply can be proved by reverse applicability. An
        # ambiguous or partially conflicted result remains available for repair.
        require(repository(root).reverse_applicable(patch), "integration_ambiguous", "Inspect partial/conflicting transfer; do not replay")
    else:
        if artifacts.read_bytes(patch):
            repository(root).apply_patch(patch)
    after = snapshot(state, root)
    require(journal["expected_tree"] and index_tree(root, task["paths"], expected["head"]) == journal["expected_tree"],
            "integration_drift", "Integration differs from the recorded Git merge; preserve and resolve explicitly")
    result = observed(effect, journal, {"before": expected["before"], "after": after, "head": repository(root).head()})
    worktree["integrated"] = True
    task["candidate"] = None
    task["integration_active"] = True
    task["freeze_base"] = expected["before"]
    # New candidate and independent integration checks/review are mandatory,
    # including clean application to a changed execution branch.
    return result
