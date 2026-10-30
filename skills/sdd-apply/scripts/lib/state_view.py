"""Small read projection of verified state, not a transition authorization API."""
from .scheduler import available


def assignments(state):
    """Show the latest assignment per scope/kind/stage, without result transcripts."""
    latest = {}
    roles = sorted((role for role in state["roles"].values() if role["kind"] == "explorer"),
                   key=lambda role: role["registered_revision"])
    for role in roles:
        assignment = role["assignment"]
        key = (role["task_id"], assignment["kind"], assignment.get("stage"))
        latest[key] = {"role_id": role["role_id"], "scope": assignment["scope"],
                       "kind": assignment["kind"], "stage": assignment.get("stage"),
                       "status": role["status"], "successor_of": role.get("successor_of")}
    return list(latest.values())


def check_progress(state, task, stage):
    """Project recorded proof metadata; acceptance still validates raw evidence."""
    from .common import digest
    from .explorer_assignments import basis
    from .verification_results import attempts
    holder = task
    evidence = [item for item in holder.get("evidence", []) if item.get("stage", "final") == stage]
    results = [item for item in holder.get("verification_results", []) if item["stage"] == stage]
    result = results[-1] if results else None
    execution = {"status": "missing", "references": [], "checks": []}
    conclusion = {"status": "missing", "id": None, "role_id": None}
    if stage in {"baseline", "self"}:
        conclusion["status"] = "not_applicable"
    baseline = holder.get("baseline_checks") if stage == "baseline" else None
    if baseline:
        from .state import snapshot
        from .verification import root_for
        statuses = {item["outcome"] for item in baseline["outputs"]}
        execution["status"] = ("passed" if statuses == {"passed"} else
                               "planned_absence" if statuses <= {"passed", "planned_absence"} else "failed")
        if baseline["run_id"] != state["run_id"] or baseline["before"] != snapshot(state, root_for(state, task)):
            execution["status"] = "stale"
        if holder.get("baseline_event", {}).get("log"):
            execution["references"] = [{"log": holder["baseline_event"]["log"]}]
        return {"execution": execution, "conclusion": conclusion}
    if result:
        conclusion.update(status=result["outcome"], id=result["id"], role_id=result["role_id"])
    if not evidence and not result and not holder.get("procedures"):
        return {"execution": execution, "conclusion": conclusion}
    try:
        # Accepted tasks retain proof of their original source and approved basis,
        # including after later tasks or an approved plan revision.
        current = result["basis"] if task["status"] == "accepted" and result else basis(state, task, "checks", stage)
        if (task["status"] != "accepted" and stage == "independent" and (task.get("worktree") or {}).get("integrated")
                and task.get("transfer")):
            # Display retained proof of the worktree source, even after cleanup.
            # This metadata projection does not authorize transfer or acceptance.
            current["source"] = task["transfer"]["snapshot"]
    except ValueError:
        execution["status"] = "unavailable"
        if result:
            conclusion["status"] = "stale"
        return {"execution": execution, "conclusion": conclusion}
    latest = {}
    for item in evidence:
        latest[item["check_id"]] = item
    statuses = []
    for check in current["checks"]:
        item = latest.get(check["id"])
        pending = holder.get("procedures", {}).get(check["id"])
        if pending and pending.get("stage", "final") == stage:
            status, reason = "pending", "procedure_pending"
        elif item is None:
            status, reason = "missing", "evidence_missing"
        else:
            role = state["roles"].get(item["role_id"], {})
            status = item["outcome"]
            if role.get("status") == "lost":
                status = "unavailable"
            elif role.get("assignment", {}).get("basis", item.get("basis")) != current:
                status = "stale"
            # A standalone procedure is not a complete check_run aggregate.
            elif item.get("procedure") and status == "passed":
                status = "pending"
            reason = "procedure_superseded" if status == "pending" else status
            execution["references"].append({"check_id": item["check_id"], "log": item["log"], "sha256": item["log_hash"]})
        statuses.append(status)
        execution["checks"].append({"check_id": check["id"], "criteria": check["criteria"],
                                    "location": check.get("location"), "status": status, "reason": reason})
    execution["status"] = next((value for value in ("failed", "unavailable", "stale", "abandoned", "pending", "missing", "skipped", "unstable")
                                if value in statuses), "passed" if statuses else "missing")
    if result and (result["basis"] != current or result["attempts_hash"] != digest(attempts(holder, stage))
                   or state["roles"].get(result["role_id"], {}).get("status") not in {"active", "finished"}
                   or result["outcome"] == "passed" and execution["status"] != "passed"):
        conclusion["status"] = "stale"
    return {"execution": execution, "conclusion": conclusion}


def task_verification(state, task):
    stages = {item["stage"] for item in task["evidence"]}
    if task.get("baseline_checks"):
        stages.add("baseline")
    stages.update(item["stage"] for item in task.get("verification_results", []))
    stages.update(item["stage"] for item in task.get("procedures", {}).values())
    return {stage: check_progress(state, task, stage) for stage in sorted(stages - {"final"})}


def compact(state):
    # Current manifest and accessed objects are verified; audit checks history.
    tasks = {}
    for key, task in state["tasks"].items():
        tasks[key] = {field: task[field] for field in (
            "status", "attempt", "blockers", "review_limit",
            "review_rounds_started", "review_rounds_completed", "active_review",
            "test_repair_limit", "test_repair_cycles_started", "active_repair",
        )}
        tasks[key]["verification"] = task_verification(state, task)
    roles = {
        key: {field: role[field] for field in ("task_id", "kind", "context_id")}
        for key, role in state["roles"].items() if role["status"] == "active"
    }
    whole = {}
    return {
        **whole,
        "view": "compact", "view_version": 1,
        **({"work_kind": state["work_kind"]} if "work_kind" in state else {}),
        **{key: state[key] for key in (
            "change_id", "run_id", "revision", "status",
            "updated_at", "blockers",
        )},
        "tasks": tasks, "active_roles": roles, "explorer_assignments": assignments(state),
        "completion": {key: state["final"].get(key) for key in ("result", "head")} if state.get("final") else None,
        "available_tasks": available(state),
        "artifacts": {"state": "state.json", "run": f"runs/{state['run_id']}"},
    }
