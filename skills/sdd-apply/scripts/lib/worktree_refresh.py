"""Rebase committed task work into a new worktree while retaining the old tree."""
from copy import deepcopy
import json
from pathlib import Path

from .repository import repository
from .common import contained, digest, require, write_json
from . import artifact_storage as artifacts
from .artifact_storage import write as atomic
from .effects import intent, observed
from .state import snapshot


def registered(root, path):
    return repository(root).worktree(path) is not None


def source_unchanged(saved):
    source = repository(saved["old"]["path"]).status(include_ignored=True)
    require(source["head"] == saved["source_commit"] and source["branch"] == saved["source_branch"]
            and not source["dirty_paths"] and not source["ignored_paths"],
            "refresh_source_changed", "Source changed; preserve both worktrees")


def finish(state, task, directory, effect, journal, resolution=None):
    saved = journal["request"]["precondition"]
    old, new = saved["old"], saved["new"]
    root = state["basis"]["project_root"]
    require(repository(root).head() == saved["base"], "refresh_head_changed", "Execution HEAD changed; preserve both trees")
    require(registered(root, new), "unregistered_worktree", "Replacement must remain registered")
    repo = repository(new)
    actual = repo.status(include_ignored=True)
    require(actual["head"] == saved["base"] and actual["branch"] == saved["branch"],
            "refresh_destination_changed", "Replacement branch changed")
    require(not repo.has_conflicts(), "refresh_conflict", "Resolve the replacement and retain the old worktree")
    require(set(actual["dirty_paths"]) <= set(task["paths"]) and not actual["ignored_paths"],
            "refresh_scope", "Preserve unexpected replacement files")
    tree = repo.tree_for_paths(task["paths"], saved["base"])
    if not resolution:
        require(journal.get("expected_tree") == tree, "refresh_destination_changed", "Replacement differs from recorded Git merge")
    source_unchanged(saved)
    task.setdefault("worktree_history", []).append({
        "worktree": deepcopy(old), "refresh_event": journal["request"]["event"]["event_id"],
        "candidate": task["candidate"], "transfer": task.get("transfer"),
        "baseline_checks": task.get("baseline_checks"), "start_snapshot": task.get("start_snapshot"),
        "active_review": task["active_review"], "active_reviewer": task.get("active_reviewer"),
        "retained": old["path"],
    })
    task["worktree"] = {**old, "path": new, "base": saved["base"], "branch": saved["branch"],
                        "snapshot": journal["baseline"], "integrated": False}
    task["worktree"].pop("inventory", None)
    task["start_snapshot"] = journal["baseline"]
    task["candidate"] = None
    for field in ("transfer", "freeze_base", "active_reviewer", "candidate_commit"):
        task.pop(field, None)
    task["active_review"] = None
    if resolution:
        task["executor"] = resolution["role_id"]
    phase = "repairing" if task["active_repair"] else "running"
    if task["status"] == "blocked":
        task["before_block"] = phase
    elif task["status"] != "pending":
        task["status"] = phase
    state["final"] = None
    return observed(effect, journal, {"worktree": task["worktree"], "retained": old["path"],
                                     "tree": tree, "resolution": resolution,
                                     "next": "Freeze a local candidate commit; run checks and review again"})


def transition(state, task, event, directory):
    require(task and task["worktree"], "worktree_required", "Refresh requires a registered task worktree")
    old = task["worktree"]
    require(task["status"] != "accepted" and not old.get("integrated") and not old.get("removed")
            and not task.get("integration_active"), "refresh_phase", "Refresh unfinished, unintegrated work only")
    require(not any(state["roles"][r]["status"] == "active" for r in task["roles"]),
            "writer_active", "Finish or reconcile all task roles before refreshing")
    require(not task.get("procedures"), "procedure_active", "Finish pending procedures")
    root = state["basis"]["project_root"]
    require(repository(root).branch() == state["basis"]["branch"], "branch_changed", "Restore execution branch")
    require(repository(root).head() == state["execution_head"], "execution_reconciliation",
            "Resume and explicitly accept the clean external HEAD before refreshing task work")
    p = event["payload"]
    resolving = event["type"] == "worktree_refresh_resolve"
    original = p.get("intent_id") if resolving else event["event_id"]
    require(isinstance(original, str) and original, "refresh_intent", "Reference the original refresh event")
    effect = artifacts.contained(directory, f"runs/{state['run_id']}/effects/{original}.json")
    for path in artifacts.paths(Path(directory) / "runs" / state["run_id"] / "effects", "*.json"):
        pending = json.loads(artifacts.read_text(path))
        if pending["phase"] == "prepared":
            operation = pending["request"]["operation"]
            require(operation != "integrate", "integration_unresolved", "Resolve pending integration first")
            require(not (operation == "worktree_refresh" and pending["request"]["task_id"] == task["plan"]["id"]
                         and path != effect), "refresh_pending", "Recover the original refresh intent")
    if resolving:
        require(artifacts.is_file(effect) and p.get("resolution") and p.get("role_id"), "refresh_resolution", "Supply intent, resolution and resolver role")
        journal = json.loads(artifacts.read_text(effect))
        require(journal["request"]["operation"] == "worktree_refresh" and journal["request"]["task_id"] == task["plan"]["id"]
                and journal["request"]["precondition"]["old"] == old and journal.get("apply_started"),
                "refresh_intent", "Expected this task's pending refresh")
        role = state["roles"].get(p["role_id"])
        require(role and role["kind"] == "executor" and role["task_id"] == task["plan"]["id"]
                and role["status"] == "finished" and role.get("trace"), "resolution_role", "Registered resolver must finish writing")
        return finish(state, task, directory, effect, journal, p)
    require(p.get("reason") and p.get("evidence"), "refresh_evidence", "Record reason and evidence for refresh")
    if artifacts.exists(effect):
        effect, journal = intent(directory, state, event, "worktree_refresh", {})
    else:
        require(registered(root, old["path"]), "unregistered_worktree", "Preserve the registered source worktree")
        source = repository(old["path"])
        status = source.status(include_ignored=True)
        require(not status["dirty_paths"] and not status["ignored_paths"], "unknown_worktree_data", "Commit owned work and preserve unknown files before refresh")
        require(source.changed_paths(old["base"]) <= set(task["paths"]), "unknown_worktree_data", "Source commits exceed task ownership")
        base = repository(root).head()
        require(base != old["base"] or not old["snapshot"].get("commit"), "refresh_unchanged", "Worktree already uses current HEAD")
        new = contained(old["workspace"], state["run_id"] + "/" + task["plan"]["id"] + "-" + event["event_id"])
        require(not new.exists() and not registered(root, new), "refresh_destination_exists", "Replacement path must be unused")
        branch = f"sdd/{state['run_id']}/{task['plan']['id']}-{event['event_id']}"
        patch = source.diff_trees(old["base"], status["head"])
        transfer = artifacts.contained(directory, f"runs/{state['run_id']}/refresh/{event['event_id']}/task.patch")
        atomic(transfer, patch)
        effect, journal = intent(directory, state, event, "worktree_refresh", {
            "old": deepcopy(old), "new": str(new), "base": base, "branch": branch,
            "source_commit": status["head"], "source_branch": status["branch"],
            "patch": str(transfer), "patch_hash": digest(patch)})
    saved = journal["request"]["precondition"]
    require("source_commit" in saved, "legacy_refresh", "Preserve old refresh intent and worktrees; reconcile explicitly before retrying")
    source_unchanged(saved)
    require(repository(root).head() == saved["base"], "refresh_head_changed", "Execution HEAD changed during refresh")
    new = Path(saved["new"])
    if not new.exists():
        require("baseline" not in journal, "refresh_destination_missing", "Replacement disappeared; preserve intent")
        new.parent.mkdir(parents=True, exist_ok=True)
        repository(root).create_worktree(new, saved["base"], saved["branch"])
    require(registered(root, new), "unregistered_worktree", "Replacement is not registered")
    repo = repository(new)
    require(repo.head() == saved["base"] and repo.branch() == saved["branch"],
            "refresh_destination_changed", "Replacement branch changed")
    if "baseline" not in journal:
        require(not repo.dirty(include_ignored=True), "refresh_destination_changed", "Replacement must begin clean")
        journal["baseline"] = snapshot(state, new)
        write_json(effect, journal)
    patch = Path(saved["patch"])
    require(digest(artifacts.read_bytes(patch)) == saved["patch_hash"], "transfer_corrupt", "Refresh transfer changed")
    pristine = not repo.dirty(include_ignored=True)
    if not journal.get("apply_started"):
        require(pristine, "refresh_destination_changed", "Replacement changed before transfer")
        journal["expected_tree"] = repo.preview_patch(saved["base"], patch)
        journal["apply_started"] = True
        write_json(effect, journal)
    if pristine and artifacts.read_bytes(patch):
        repo.apply_patch(patch)
    return finish(state, task, directory, effect, journal)
