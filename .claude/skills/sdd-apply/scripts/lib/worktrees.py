"""Registered detached task worktrees, preserving unfinished and unknown data."""
from pathlib import Path
import json
from .common import contained, digest, git, require
from .effects import intent, observed
from .state import snapshot
from .scheduler import available


def inventory(path):
    """Include ignored data before any destructive cleanup."""
    root = Path(path).resolve()
    files = {}
    for item in root.rglob("*"):
        relative = item.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        require(not item.is_symlink() and not (hasattr(item, "is_junction") and item.is_junction()), "worktree_link", relative)
        if item.is_file():
            files[relative] = digest(item.read_bytes())
    return files


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task required")
    root = state["basis"]["project_root"]
    if event["type"] == "worktree_create":
        require(state["mode"] == "parallel" and state["parallel_request"], "parallel_required", "Explicit parallel request required")
        require(task["plan"]["id"] in available(state) and not task["worktree"], "worktree_admission", "Task is not available")
        workspace = Path(event["payload"]["workspace"]).resolve()
        resources = event["payload"].get("resources", [])
        require(isinstance(resources, list) and all(isinstance(r, str) and r for r in resources), "resource_schema", "Use explicit resource names")
        occupied = {r for t in state["tasks"].values() if t is not task and t["worktree"] and t["status"] != "accepted" for r in t["worktree"]["resources"]}
        require(not occupied & set(resources), "shared_resources", "Allocate separate ports/databases/temp resources or serialize")
        require(not any(p in {"skills", ".agents", ".claude"} for p in workspace.parts), "runtime_path", "Worktrees belong outside skill collections")
        path = contained(workspace, state["run_id"] + "/" + task["plan"]["id"])
        base = git(root, "rev-parse", "HEAD")
        effect, journal = intent(directory, state, event, "worktree_create", {"path": str(path), "base": base})
        expected = journal["request"]["precondition"]
        require(expected["path"] == str(path), "worktree_path", "Intent path mismatch")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            git(root, "worktree", "add", "--detach", str(path), expected["base"])
        listing = git(root, "worktree", "list", "--porcelain").replace("\\", "/")
        require(str(path).replace("\\", "/") in listing, "unregistered_worktree", "Existing path is not this repository's worktree")
        require(git(path, "rev-parse", "HEAD") == expected["base"] and not git(path, "symbolic-ref", "-q", "HEAD", check=False), "worktree_changed", "Expected detached original HEAD")
        task["worktree"] = {"path": str(path), "workspace": str(workspace), "base": expected["base"], "owner": state["owner"], "integrated": False, "resources": event["payload"].get("resources", []), "snapshot": snapshot(state, path), "inventory": inventory(path)}
        return observed(effect, journal, task["worktree"])
    worktree = task["worktree"]
    require(worktree and task["status"] == "accepted" and task["commits"], "worktree_unaccepted", "Preserve unaccepted work")
    from .commits import confirm
    confirm(state, task, task["commits"][-1])
    effect_path = contained(directory, f"runs/{state['run_id']}/effects/{event['event_id']}.json")
    if effect_path.exists() and not Path(worktree["path"]).exists():
        effect, journal = intent(directory, state, event, "worktree_remove", {})
        listing = git(root, "worktree", "list", "--porcelain").replace("\\", "/")
        require(worktree["path"].replace("\\", "/") not in listing, "worktree_remove_ambiguous", "Git still registers the missing worktree")
        worktree["removed"] = True
        return observed(effect, journal, {"removed": worktree["path"]})
    require(not any(state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "All task roles must have stopped")
    require(task.get("transfer") and task["transfer"]["snapshot"] == snapshot(state, worktree["path"]), "unknown_worktree_data", "Preserve unknown or changed files")
    actual = inventory(worktree["path"])
    require(actual == task["transfer"]["inventory"], "unknown_worktree_data", "Preserve changed or ignored data not saved in the transfer")
    initial = worktree["inventory"]
    changed = {p for p in set(initial) | set(actual) if initial.get(p) != actual.get(p)}
    require(changed <= set(task["paths"]), "unknown_worktree_data", "Preserve files outside task ownership")
    path = contained(worktree["workspace"], str(Path(worktree["path"]).relative_to(worktree["workspace"])))
    require(str(path) == worktree["path"], "worktree_escape", "Unregistered path")
    effect, journal = intent(directory, state, event, "worktree_remove", {"path": str(path), "inventory": actual, "sha": task["commits"][-1]["sha"]})
    require(journal["phase"] == "prepared", "worktree_recreated", "Preserve data at a previously removed path")
    git(root, "worktree", "remove", "--force", str(path))
    worktree["removed"] = True
    return observed(effect, journal, {"removed": str(path)})
