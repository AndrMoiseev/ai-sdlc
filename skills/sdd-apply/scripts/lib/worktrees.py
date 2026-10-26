"""Registered task branches and worktrees, preserving unfinished and unknown data."""
from .repository import repository
from .path_resolution import resolve
from pathlib import Path
import json
from . import artifact_storage as artifacts
from .common import contained, digest, require
from .effects import intent, observed
from .state import snapshot
from .scheduler import available


def inventory(path):
    """List unknown paths for conservative cleanup; never hash source files."""
    return repository(path).status(include_ignored=True)


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task required")
    root = state["basis"]["project_root"]
    if event["type"] == "worktree_create":
        repairing = task["status"] == "repairing" and not task["worktree"]
        require((task["plan"]["id"] in available(state) or repairing) and not task["worktree"], "worktree_admission", "Task is not available")
        workspace = resolve(event["payload"]["workspace"])
        resources = event["payload"].get("resources", [])
        require(isinstance(resources, list) and all(isinstance(r, str) and r for r in resources), "resource_schema", "Use explicit resource names")
        occupied = {r for t in state["tasks"].values() if t is not task and t["worktree"] and t["status"] != "accepted" for r in t["worktree"]["resources"]}
        require(not occupied & set(resources), "shared_resources", "Allocate separate ports/databases/temp resources or serialize")
        require(not any(p in {"skills", ".agents", ".claude"} for p in workspace.parts), "runtime_path", "Worktrees belong outside skill collections")
        suffix = "-" + event["event_id"] if repairing else ""
        path = contained(workspace, state["run_id"] + "/" + task["plan"]["id"] + suffix)
        base = repository(root).head()
        branch = f"sdd/{state['run_id']}/{task['plan']['id']}{suffix}"
        effect, journal = intent(directory, state, event, "worktree_create", {"path": str(path), "base": base, "branch": branch})
        expected = journal["request"]["precondition"]
        require(expected["path"] == str(path), "worktree_path", "Intent path mismatch")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            repository(root).create_worktree(path, expected["base"], expected["branch"])
        require(repository(root).worktree(path) is not None, "unregistered_worktree", "Existing path is not this repository's worktree")
        require(repository(path).head() == expected["base"] and repository(path).branch() == expected["branch"], "worktree_changed", "Expected registered task branch at original HEAD")
        task["worktree"] = {"path": str(path), "workspace": str(workspace), "base": expected["base"], "branch": expected["branch"], "owner": state["owner"], "integrated": False, "resources": event["payload"].get("resources", []), "snapshot": snapshot(state, path)}
        if repairing:
            task["start_snapshot"] = task["worktree"]["snapshot"]
        return observed(effect, journal, task["worktree"])
    worktree = task["worktree"]
    require(worktree and task["status"] == "accepted" and task["commits"], "worktree_unaccepted", "Preserve unaccepted work")
    from .commits import confirm
    confirm(state, task, task["commits"][-1])
    effect_path = artifacts.contained(directory, f"runs/{state['run_id']}/effects/{event['event_id']}.json")
    if artifacts.exists(effect_path) and not Path(worktree["path"]).exists():
        effect, journal = intent(directory, state, event, "worktree_remove", {})
        require(repository(root).worktree(worktree["path"]) is None, "worktree_remove_ambiguous", "Git still registers the missing worktree")
        worktree["removed"] = True
        return observed(effect, journal, {"removed": worktree["path"]})
    require(not any(state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "All task roles must have stopped")
    require(task.get("transfer") and task["transfer"]["snapshot"] == snapshot(state, worktree["path"]), "unknown_worktree_data", "Preserve unknown or changed files")
    actual = inventory(worktree["path"])
    require(not actual["dirty_paths"] and not actual["ignored_paths"], "unknown_worktree_data", "Preserve changed, untracked or ignored worktree data")
    require(repository(worktree["path"]).changed_paths(worktree["base"]) <= set(task["paths"]), "unknown_worktree_data", "Preserve commits outside task ownership")
    path = contained(worktree["workspace"], str(Path(worktree["path"]).relative_to(worktree["workspace"])))
    require(str(path) == worktree["path"], "worktree_escape", "Unregistered path")
    effect, journal = intent(directory, state, event, "worktree_remove", {"path": str(path), "head": actual["head"], "sha": task["commits"][-1]["sha"]})
    require(journal["phase"] == "prepared", "worktree_recreated", "Preserve data at a previously removed path")
    repository(root).remove_worktree(path)
    worktree["removed"] = True
    return observed(effect, journal, {"removed": str(path)})
