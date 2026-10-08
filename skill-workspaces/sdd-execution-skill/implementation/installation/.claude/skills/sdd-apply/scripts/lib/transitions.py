"""Single event router; unavailable mandatory operations fail closed."""
from .common import require
from .state import assert_basis, snapshot
from .scheduler import available


def reduce(state, event, directory):
    kind, payload = event["type"], event["payload"]
    task = state["tasks"].get(event["task_id"])
    require(isinstance(payload, dict), "payload", "Object required")
    if kind == "block":
        require(payload.get("reason") and payload.get("resume_condition"), "block_reason", "Reason and resume condition required")
        if task:
            task["before_block"] = task["status"]
            task["status"] = "blocked"
            task["blockers"].append(payload)
        if not task or state["mode"] == "sequential":
            state["status"] = "blocked"
            state["blockers"].append({**payload, "task_id": event["task_id"]})
        return {"blocked": payload}
    if kind in {"resume", "spec_conflict", "revised_plan", "handoff", "mode"}:
        from .resume import transition
        return transition(state, task, event, directory)
    if kind == "budget_extend":
        from .budgets import extend
        return extend(state, task, payload)
    # Results of already-running external work can be recorded while blocked.
    if kind not in {"role_result", "review_result", "role_register", "finalize"}:
        require(state["status"] == "active" and not state["blockers"], "run_blocked", str(state["blockers"]))
    if kind != "role_result":
        assert_basis(state)
    if kind == "role_register" and state["status"] != "active":
        predecessor = state["roles"].get(payload.get("successor_of"))
        require(predecessor and predecessor["status"] == "lost" and predecessor["task_id"] == event["task_id"] and all(b["reason"] == "lost_role" for b in state["blockers"]), "run_blocked", "Only a lost-role successor may be registered while blocked")
    if kind in {"role_register", "role_result", "review_start", "review_result"}:
        from .roles import transition
        return transition(state, task, event, directory)
    if kind in {"checks_register", "checks_extend", "check_setup", "check_run", "candidate", "procedure_begin", "procedure_result"}:
        from .verification import transition
        return transition(state, task, event, directory)
    if kind == "start":
        require(event["task_id"] in available(state), "task_unavailable", "Dependencies or execution mode prevent admission")
        require((directory / "dashboard.html").is_file(), "dashboard_missing", "Generate the initial dashboard before starting")
        require(task["checks"], "checks_missing", "Register planned and project checks first")
        role = state["roles"].get(payload.get("role_id"))
        require(role and role["kind"] == "executor" and role["task_id"] == event["task_id"] and role["status"] == "active", "executor_missing", "Register a fresh executor")
        paths = payload.get("paths", [])
        require(paths and len(paths) == len(set(paths)), "task_paths", "Explicit owned paths required")
        from .common import contained
        for path in paths:
            from pathlib import PurePosixPath, Path
            require(isinstance(path, str) and not Path(path).is_absolute() and "\\" not in path and ":" not in path and str(PurePosixPath(path)) == path and ".." not in PurePosixPath(path).parts, "task_paths", "Use canonical project-relative file paths")
            owned = contained(state["basis"]["project_root"], path)
            require(not owned.is_dir(), "task_paths", "List each owned file; directories obscure mixed ownership")
        occupied = {p.casefold() for key, t in state["tasks"].items() if key != event["task_id"] and t["status"] not in {"pending", "accepted"} for p in t["paths"]}
        require(not occupied & {p.casefold() for p in paths}, "shared_files", "Another unfinished task owns one of these files")
        if state["mode"] == "parallel":
            require(task["worktree"], "worktree_missing", "Parallel tasks need registered worktrees")
        task.update(status="running", paths=paths, executor=payload["role_id"], attempt=task["attempt"] + 1)
        task["start_snapshot"] = snapshot(state, task["worktree"]["path"] if task["worktree"] else None)
        return {"status": "running"}
    if kind == "repair":
        from .budgets import repair
        return repair(state, task, payload)
    if kind in {"commit", "accept"}:
        from .commits import transition
        return transition(state, task, event, directory)
    if kind in {"worktree_create", "worktree_remove"}:
        from .worktrees import transition
        return transition(state, task, event, directory)
    if kind in {"integrate", "transfer", "integration_resolve"}:
        from .integration import transition
        return transition(state, task, event, directory)
    if kind == "finalize":
        from .finalize import finalize
        return finalize(state, payload, directory)
    raise ValueError(f"unknown_event: {kind}")
