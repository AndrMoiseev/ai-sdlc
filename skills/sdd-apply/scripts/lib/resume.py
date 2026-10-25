"""Reconcile execution against normative bytes, Git and host observations."""
from .repository import repository
from copy import deepcopy
from pathlib import Path
from . import artifact_storage as artifacts
from .common import digest, require, write_json
from .state import assert_basis, snapshot


def transition(state, task, event, directory):
    p, kind = event["payload"], event["type"]
    if kind == "spec_conflict":
        require(p.get("reproduction") and p.get("criteria") and p.get("contract"), "conflict_evidence", "Record reproduction, AC and conflicting contract")
        path = artifacts.contained(directory, f"runs/{state['run_id']}/spec-return/{event['event_id']}.json")
        write_json(path, {"task_id": event["task_id"], "basis": state["basis"]["manifest"], **p})
        state["blockers"].append({"reason": "spec_conflict", "task_id": event["task_id"], "resume_condition": "Revised approved plan and execution instruction", "material": str(path)})
        state["status"] = "blocked"
        return {"return_to": "sdd-spec", "material": str(path)}
    if kind == "mode":
        require(p.get("mode") in {"sequential", "parallel"} and p.get("source") and p.get("text"), "mode_decision", "Record the actual user's mode decision")
        mode = p["mode"]
        if mode == "parallel" and not p.get("isolation_available"):
            return {"mode": state["mode"], "limitation": "worktree isolation unavailable"}
        require(mode != state["mode"], "mode_unchanged", "Already in this mode")
        state["pending_mode"] = {"mode": mode, "decision": p}
        state["blockers"].append({"reason": "mode_handoff", "resume_condition": "Fresh orchestrator context with only the new flow"})
        state["status"] = "blocked"
        return {"handoff_required": mode}
    if kind == "handoff":
        require(p.get("new_owner") and p["new_owner"] != state["owner"] and p.get("fresh") is True and p.get("launch_ref"), "handoff_context", "Actual fresh host context required")
        state["previous_owner"] = state["owner"]
        state["owner"] = p["new_owner"]
        pending = state.pop("pending_mode", None)
        if pending:
            state["mode"] = pending["mode"]
            state["parallel_request"] = pending["decision"] if state["mode"] == "parallel" else None
            state["blockers"] = [b for b in state["blockers"] if b["reason"] != "mode_handoff"]
        state["status"] = "blocked" if state["blockers"] else "active"
        return {"owner": state["owner"], "mode": state["mode"], "status": state["status"]}
    if kind == "revised_plan":
        require(not state.get("pending_mode"), "mode_handoff", "Complete the pending mode handoff before replacing the basis")
        require(not any(r["status"] == "active" for r in state["roles"].values()), "active_roles", "Finish or reconcile active roles before replacing the basis")
        from .inputs import validate, basis_dependency
        import uuid
        basis = validate(state["basis"]["project_root"], state["change_id"], p.get("instruction"),
                         sdd_shared=basis_dependency(state["basis"]), work_kind=state["basis"].get("work_kind", "change"))
        require(basis["manifest"] != state["basis"]["manifest"], "plan_unchanged", "Use resume when the approved basis is unchanged")
        plans = {plan["id"]: plan for plan in basis["tasks"]}
        completed = [key for key, old in state["tasks"].items() if old["status"] == "accepted"]
        for key in completed:
            require(plans.get(key) == state["tasks"][key]["plan"], "completed_task_changed",
                    f"Preserve completed task {key} unchanged; append follow-up work as a new task")
        # Validate before archiving or creating a run so rejected revisions have
        # no side effects. New tasks follow the existing plan in file and number order.
        last_number = max([old["plan"]["number"] for old in state["tasks"].values()]
                          + [plan["number"] for plan in basis["tasks"] if plan["id"] in state["tasks"]])
        appended = False
        for plan in basis["tasks"]:
            if plan["id"] in state["tasks"]:
                require(not appended, "new_tasks_append_only", "Append new tasks after all existing tasks")
            else:
                appended = True
                require(plan["number"] > last_number, "new_tasks_append_only", "Number new tasks after the existing plan")
        previous_run = state["run_id"]
        from .state_objects import StateObjects
        objects = StateObjects(directory)
        write_json(artifacts.contained(directory, f"runs/{previous_run}/superseded-state.json"), objects.pack(state, root=True))
        previous_tasks = deepcopy(state["tasks"])
        state["run_id"] = uuid.uuid4().hex
        state["previous_run"] = previous_run
        state["basis"] = basis
        if basis.get("work_kind", "change") == "refactoring":
            state.update(work_kind="refactoring", **{kind: {record["id"]: record for record in basis[kind]}
                         for kind in ("acceptance", "verification")})
        state["tasks"] = {}
        from .state import new_task
        for plan in basis["tasks"]:
            old = previous_tasks.get(plan["id"])
            if old and old["status"] == "accepted":
                state["tasks"][plan["id"]] = old
                continue
            fresh = new_task(plan)
            if old:
                for field in ("review_limit", "review_rounds_started", "review_rounds_completed", "test_repair_limit", "test_repair_cycles_started", "active_repair", "repair_cycles", "budget_decisions", "commits"):
                    fresh[field] = old[field]
                fresh["prior_result"] = {"$object": objects.put(objects.pack(old, root=True))}
            state["tasks"][plan["id"]] = fresh
        if state["mode"] == "parallel":
            state["parallel_request"] = basis["instruction"]
        # Budget blockers survive a revised plan. Other old blockers are retained
        # in the archived run and checked again against the new basis.
        state["blockers"] = [b for b in state["blockers"] if b["reason"] in {"review_limit_reached", "test_repair_limit_reached"}]
        state["status"] = "blocked" if state["blockers"] else "active"
        state["baseline"] = snapshot(state)
        state["final"] = None
        write_json(artifacts.contained(directory, f"runs/{state['run_id']}/input.json"), objects.pack(basis, root=True))
        return {"run_id": state["run_id"], "previous_run": previous_run, "preserved_tasks": completed,
                "reassessment": "Completed tasks preserved; unfinished tasks require reassessment"}
    require(kind == "resume", "resume_operation", kind)
    from .check_registry import recovery
    registries = recovery(state)
    issues = []
    try:
        assert_basis(state)
        state["blockers"] = [b for b in state["blockers"] if b["reason"] != "normative_drift"]
    except ValueError as exc:
        issues.append({"reason": "normative_drift", "detail": str(exc), "resume_condition": "Restore approved bytes or use revised_plan"})
    root = state["basis"]["project_root"]
    if repository(root).branch() != state["basis"]["branch"]:
        issues.append({"reason": "branch_changed", "resume_condition": "Restore execution branch"})
    require(p.get("host_trace") and isinstance(p.get("live_contexts"), list), "host_observation", "Supply actual host role liveness observation")
    for role in state["roles"].values():
        if role["status"] == "active" and role["context_id"] not in p["live_contexts"]:
            role["status"] = "lost"
            t = state["tasks"].get(role["task_id"])
            if t and t["status"] not in {"pending", "accepted"}:
                if t["status"] != "blocked":
                    t["before_block"] = t["status"]
                t["status"] = "blocked"
                item = {"reason": "lost_role", "task_id": role["task_id"], "role_id": role["role_id"], "resume_condition": "Register a fresh successor with preserved files and task packet"}
                t["blockers"].append(item)
                issues.append(item)
    for key, t in state["tasks"].items():
        if t["candidate"] and t["status"] not in {"accepted", "pending", "blocked"}:
            from .verification import candidate
            from .candidates import same
            try:
                unchanged = same(state, t["candidate"], candidate(state, t))
            except ValueError:
                unchanged = False
            if not unchanged:
                issues.append({"reason": "candidate_drift", "task_id": key, "resume_condition": "Rebaseline legacy evidence or re-freeze and independently verify the changed local commit"})
    for issue in issues:
        if issue not in state["blockers"]:
            state["blockers"].append(issue)
    # Clearing semantic blockers needs a recorded resolution. Budgets and
    # normative drift cannot be waived by this generic resume operation.
    resolutions = p.get("resolutions", [])
    for resolution in resolutions:
        require(resolution.get("evidence") and resolution.get("reason") not in {"review_limit_reached", "test_repair_limit_reached", "normative_drift", "spec_conflict", "mode_handoff", "mode_switch_worktree"}, "resume_resolution", "Use the dedicated operation for this blocker")
        reason = resolution["reason"]
        lost_role = None
        if reason == "lost_role":
            successor = state["roles"].get(resolution.get("successor"))
            require(successor and successor["status"] == "active" and successor.get("successor_of") and successor["task_id"] == resolution.get("task_id"), "successor_required", "Register a fresh successor first")
            # Older requests omit role_id; the registered lineage identifies the
            # one loss they resolve. Never clear another lost role on this task.
            lost_role = resolution.get("role_id", successor["successor_of"])
            predecessor = state["roles"].get(lost_role)
            require(predecessor and successor["successor_of"] == lost_role
                    and predecessor["status"] == "lost"
                    and predecessor["task_id"] == successor["task_id"]
                    and predecessor["kind"] == successor["kind"],
                    "successor_required", "Successor must replace the named lost role with the same task and kind")
            require(any(b["reason"] == reason and b.get("task_id") == resolution.get("task_id")
                        and b.get("role_id") == lost_role for b in state["blockers"]),
                    "successor_required", "No unresolved loss for this role")
        def resolved(blocker):
            return (blocker["reason"] == reason
                    and blocker.get("task_id", resolution.get("task_id")) == resolution.get("task_id")
                    and (lost_role is None or blocker.get("role_id") == lost_role))
        state["blockers"] = [b for b in state["blockers"] if not
                             (b.get("task_id") == resolution.get("task_id") and resolved(b))]
        t = state["tasks"].get(resolution.get("task_id"))
        if t:
            if reason == "lost_role" and successor["kind"] == "executor":
                t["executor"] = successor["role_id"]
            if reason == "lost_role" and successor["kind"] == "reviewer" and t.get("active_reviewer") == lost_role and t["active_review"]:
                t["active_reviewer"] = successor["role_id"]
            t["blockers"] = [b for b in t["blockers"] if not resolved(b)]
            if not t["blockers"] and t["status"] == "blocked":
                target = t.get("before_block", "running")
                if target == "accepted":
                    from .commits import confirm, reviewed
                    from .verification import valid_evidence
                    valid_evidence(state, t, directory)
                    reviewed(state, t)
                    require(t["commits"], "commit_required", "Accepted task needs confirmed commits")
                    confirm(state, t, t["commits"][-1])
                t["status"] = target
    state["status"] = "blocked" if state["blockers"] else "active"
    head = repository(root).head()
    stale_worktrees = [{"task_id": key, "path": t["worktree"]["path"], "base": t["worktree"]["base"],
                       "head": head, "next": "worktree_refresh"}
                      for key, t in state["tasks"].items()
                      if t["status"] != "accepted" and t["worktree"]
                      and not t["worktree"].get("integrated") and not t["worktree"].get("removed")
                      and t["worktree"]["base"] != head]
    return {"status": state["status"], "issues": issues, "preserved_roles": state["roles"],
            "stale_worktrees": stale_worktrees, **({"check_registries": registries} if registries else {})}
