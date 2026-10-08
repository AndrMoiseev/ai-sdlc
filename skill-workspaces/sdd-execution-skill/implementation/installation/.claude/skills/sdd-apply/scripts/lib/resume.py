"""Reconcile execution against normative bytes, Git and host observations."""
from copy import deepcopy
from pathlib import Path
from .common import contained, digest, git, require, write_json
from .state import assert_basis, snapshot


def transition(state, task, event, directory):
    p, kind = event["payload"], event["type"]
    if kind == "spec_conflict":
        require(p.get("reproduction") and p.get("criteria") and p.get("contract"), "conflict_evidence", "Record reproduction, AC and conflicting contract")
        path = contained(directory, f"runs/{state['run_id']}/spec-return/{event['event_id']}.json")
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
            if state["mode"] == "sequential" and any(t["worktree"] and not t["worktree"].get("integrated") and t["status"] != "accepted" for t in state["tasks"].values()):
                state["blockers"].append({"reason": "mode_switch_worktree", "resume_condition": "User resolution of preserved worktree candidates; no automatic integration"})
        state["status"] = "blocked" if state["blockers"] else "active"
        return {"owner": state["owner"], "mode": state["mode"], "status": state["status"]}
    if kind == "revised_plan":
        require(not any(r["status"] == "active" for r in state["roles"].values()), "active_roles", "Finish or reconcile active roles before replacing the basis")
        from .inputs import validate
        import uuid
        basis = validate(state["basis"]["project_root"], state["change_id"], p.get("instruction"), state["basis"]["sdd_spec"])
        require(basis["manifest"] != state["basis"]["manifest"], "plan_unchanged", "Use resume when the approved basis is unchanged")
        previous_run = state["run_id"]
        write_json(contained(directory, f"runs/{previous_run}/superseded-state.json"), state)
        previous_tasks = deepcopy(state["tasks"])
        state["run_id"] = uuid.uuid4().hex
        state["previous_run"] = previous_run
        state["basis"] = basis
        state["tasks"] = {}
        from .state import new_task
        for plan in basis["tasks"]:
            fresh = new_task(plan)
            old = previous_tasks.get(plan["id"])
            if old:
                for field in ("review_limit", "review_rounds_started", "review_rounds_completed", "test_repair_limit", "test_repair_cycles_started", "active_repair", "repair_cycles", "budget_decisions", "commits"):
                    fresh[field] = old[field]
                fresh["prior_result"] = old
            state["tasks"][plan["id"]] = fresh
        state["mode"], state["parallel_request"] = "sequential", None
        # Budget blockers survive a revised plan. Other old blockers are retained
        # in the archived run and checked again against the new basis.
        state["blockers"] = [b for b in state["blockers"] if b["reason"] in {"review_limit_reached", "test_repair_limit_reached"}]
        state["status"] = "blocked" if state["blockers"] else "active"
        state["baseline"] = snapshot(state)
        state["final"] = None
        write_json(contained(directory, f"runs/{state['run_id']}/input.json"), basis)
        return {"run_id": state["run_id"], "previous_run": previous_run, "reassessment": "No task accepted automatically"}
    require(kind == "resume", "resume_operation", kind)
    issues = []
    try:
        assert_basis(state)
        state["blockers"] = [b for b in state["blockers"] if b["reason"] != "normative_drift"]
    except ValueError as exc:
        issues.append({"reason": "normative_drift", "detail": str(exc), "resume_condition": "Restore approved bytes or use revised_plan"})
    root = state["basis"]["project_root"]
    if git(root, "symbolic-ref", "--quiet", "--short", "HEAD") != state["basis"]["branch"]:
        issues.append({"reason": "branch_changed", "resume_condition": "Restore execution branch"})
    require(p.get("host_trace") and isinstance(p.get("live_contexts"), list), "host_observation", "Supply actual host role liveness observation")
    for role in state["roles"].values():
        if role["status"] == "active" and role["context_id"] not in p["live_contexts"]:
            role["status"] = "lost"
            t = state["tasks"].get(role["task_id"])
            if t and t["status"] not in {"pending", "accepted"}:
                t["before_block"] = t["status"]
                t["status"] = "blocked"
                item = {"reason": "lost_role", "task_id": role["task_id"], "role_id": role["role_id"], "resume_condition": "Register a fresh successor with preserved files and task packet"}
                t["blockers"].append(item)
                issues.append(item)
    for key, t in state["tasks"].items():
        if t["candidate"] and t["status"] not in {"accepted", "pending", "blocked"}:
            from .verification import candidate
            if t["candidate"] != candidate(state, t):
                issues.append({"reason": "candidate_drift", "task_id": key, "resume_condition": "Re-freeze and independently verify changed candidate"})
    for issue in issues:
        if issue not in state["blockers"]:
            state["blockers"].append(issue)
    # Clearing semantic blockers needs a recorded resolution. Budgets and
    # normative drift cannot be waived by this generic resume operation.
    resolutions = p.get("resolutions", [])
    for resolution in resolutions:
        require(resolution.get("evidence") and resolution.get("reason") not in {"review_limit_reached", "test_repair_limit_reached", "normative_drift", "spec_conflict", "mode_handoff", "mode_switch_worktree"}, "resume_resolution", "Use the dedicated operation for this blocker")
        reason = resolution["reason"]
        if reason == "lost_role":
            successor = state["roles"].get(resolution.get("successor"))
            require(successor and successor["status"] == "active" and successor.get("successor_of") and successor["task_id"] == resolution.get("task_id"), "successor_required", "Register a fresh successor first")
        state["blockers"] = [b for b in state["blockers"] if not (b["reason"] == reason and b.get("task_id") == resolution.get("task_id"))]
        t = state["tasks"].get(resolution.get("task_id"))
        if t:
            if reason == "lost_role" and successor["kind"] == "executor":
                t["executor"] = successor["role_id"]
            if reason == "lost_role" and successor["kind"] == "reviewer" and t["active_review"]:
                t["active_reviewer"] = successor["role_id"]
            t["blockers"] = [b for b in t["blockers"] if b["reason"] != reason]
            if not t["blockers"] and t["status"] == "blocked":
                target = t.get("before_block", "running")
                if target == "accepted":
                    from .commits import confirm, reviewed
                    from .verification import valid_evidence
                    valid_evidence(state, t, directory)
                    reviewed(t)
                    require(t["commits"], "commit_required", "Accepted task needs confirmed commits")
                    confirm(state, t, t["commits"][-1])
                t["status"] = target
    state["status"] = "blocked" if state["blockers"] else "active"
    return {"status": state["status"], "issues": issues, "preserved_roles": state["roles"]}
