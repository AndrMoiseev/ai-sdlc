"""Host-attested fresh contexts and separate implementation/review results."""
from .common import contained, digest, now, require, write_json
from .verification import current, independent, valid_evidence
from .review_policy import proven
import re


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task required")
    p, kind = event["payload"], event["type"]
    if kind == "role_register":
        require(set(p) >= {"role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"}, "role_schema", "Host context and launch evidence required")
        require(p["kind"] in {"executor", "verifier", "reviewer", "final_verifier"} and p["fresh"] is True, "fresh_role", "A fresh context is mandatory")
        require(p["host"] in {"codex", "claude-code"} and p["launch_ref"] and p["context_id"], "host_evidence", "Record actual host launch; do not simulate a role")
        require(p["role_id"] not in state["roles"], "duplicate_role", "Role already registered")
        require(isinstance(p["role_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", p["role_id"]), "role_id", "Use a filesystem-safe role ID")
        require(p["context_id"] != state["owner"], "orchestrator_role", "Use a separate context")
        if p["kind"] == "executor":
            require(not any(state["roles"][r]["kind"] == "executor" and state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "Finish or reconcile the previous executor before assigning another")
        for role in state["roles"].values():
            if role["context_id"] == p["context_id"]:
                require(role["task_id"] == task["plan"]["id"] and role["kind"] in {"reviewer", "verifier"} and p["kind"] in {"reviewer", "verifier"}, "context_reused", "Only verifier/reviewer of the same task may share a fresh context")
        require(p["capabilities"].get("fresh_context") is True, "host_limits", "Fresh context mechanism unavailable; distinguish busy slots from unsupported host")
        role = {**p, "task_id": task["plan"]["id"], "status": "active", "registered_at": now()}
        state["roles"][p["role_id"]] = role
        task["roles"].append(p["role_id"])
        packet = {"task": task["plan"], "basis": state["basis"]["manifest"], "project_root": state["basis"]["project_root"], "paths": task["paths"], "worktree": task["worktree"], "candidate": task["candidate"], "checks": task["checks"], "prior_commits": task["commits"], "blockers": task["blockers"], "rejected_approaches": task.get("rejected_approaches", []), "role": role}
        path = contained(directory, f"runs/{state['run_id']}/roles/{p['role_id']}.json")
        write_json(path, packet)
        return {"role": role, "packet": str(path)}
    if kind == "role_result":
        role = state["roles"].get(p.get("role_id"))
        require(role and role["task_id"] == task["plan"]["id"] and role["status"] == "active", "role_missing", "Active registered role required")
        require(p.get("result") and p.get("trace"), "role_result", "Result and host trace required")
        role.update(status="finished", result=p["result"], trace=p["trace"])
        # Executor DONE is deliberately only a role result.
        return {"role_finished": p["role_id"], "task_status": task["status"]}
    if kind == "review_start":
        require(task["status"] in {"verifying", "reviewing", "integrating"}, "review_phase", "Verification precedes review")
        independent(state, task, p.get("role_id"), {"reviewer"})
        valid_evidence(state, task, directory, "integration" if task.get("worktree", {}) and task["worktree"].get("integrated") else None)
        from .budgets import reserve_review
        if not reserve_review(state, task, event["event_id"]):
            return {"blocked": "review_limit_reached"}
        task["active_reviewer"] = p["role_id"]
        task["status"] = "reviewing"
        return {"round": task["review_rounds_started"], "candidate": task["candidate"]}
    require(kind == "review_result", "role_operation", kind)
    require(task["active_review"] and task.get("active_reviewer") == p.get("role_id"), "review_not_started", "Reserve review round first")
    independent(state, task, p["role_id"], {"reviewer"})
    current(state, task)
    require(p.get("candidate") == task["candidate"], "stale_review", "Review must name the frozen candidate")
    require(p.get("verdict") in {"pass", "changes", "more_checks"} and isinstance(p.get("findings"), list), "review_schema", "Verdict and findings required")
    require(p.get("test_integrity") and p.get("trace"), "review_evidence", "Review assertions, skips/xfail and command weakening; retain trace")
    findings = []
    for finding in p["findings"]:
        require(isinstance(finding, dict), "finding_schema", "Finding must be an object")
        require(set(finding) >= {"severity", "criteria", "path", "problem", "resolution"}, "finding_schema", "Findings need AC, file and resolution condition")
        require(finding["severity"] in {"blocker", "recommendation"}, "finding_severity", "Unknown severity")
        findings.append({**finding, "reported_severity": finding["severity"],
                         "severity": "blocker" if proven(finding) else "recommendation"})
    blockers = any(f["severity"] == "blocker" for f in findings)
    require(p["verdict"] != "pass" or not blockers, "review_blocker", "Pass conflicts with proven violations")
    verdict = "pass" if p["verdict"] == "changes" and not blockers else p["verdict"]
    result = {**p, "verdict": verdict, "reported_verdict": p["verdict"], "findings": findings,
              "round_id": task["active_review"], "round": task["review_rounds_started"]}
    task["reviews"].append(result)
    task["review_rounds_completed"] += 1
    task["active_review"] = None
    state["roles"][p["role_id"]]["status"] = "finished"
    if verdict == "pass":
        task["status"] = "integrating" if task["worktree"] and not task["worktree"].get("integrated") else "committing"
    elif verdict == "more_checks":
        task["status"] = "verifying"
    else:
        from .budgets import failure
        failure(state, task, "review", "changes_requested")
    return {"verdict": verdict, "status": task["status"]}
