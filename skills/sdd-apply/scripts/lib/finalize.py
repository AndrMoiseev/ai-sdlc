"""Complete the plan from accepted tasks; no final execution or agent assessment."""
from .repository import repository
from .common import now, require
from .commits import confirm
from .state import snapshot, clean_source
from .verification import local_criteria
from .review_policy import technical_debt


def finalize(state, payload, directory):
    root = state["basis"]["project_root"]
    repo = repository(root)
    head = repo.head()
    # Obsolete final-check blockers do not require a removed role or rerun.
    state["blockers"] = [b for b in state["blockers"]
                         if b["reason"] not in {"final_incomplete", "completion_incomplete"}]
    missing = [{"reason": b["reason"], "criteria": [], "task_id": b.get("task_id")}
               for b in state["blockers"]]
    accepted, evidence, conclusions = [], [], []
    try:
        clean_source(snapshot(state))
        require(head == state["execution_head"] and repo.branch() == state["basis"]["branch"],
                "execution_reconciliation", "Reconcile the execution branch before completion")
    except ValueError as exc:
        missing.append({"criteria": [], "reason": str(exc)})
    for key, task in state["tasks"].items():
        criteria = sorted(local_criteria(state, task))
        if task["status"] != "accepted" or not task["commits"]:
            missing.append({"task_id": key, "criteria": criteria, "reason": "task_not_accepted"})
            continue
        try:
            for commit in task["commits"]:
                confirm(state, task, commit)
            result = next((r for r in reversed(task.get("verification_results", []))
                           if r["stage"] in {"independent", "integration"}), None)
            require(result and result["outcome"] == "passed", "verification_missing", "Accepted task must retain its passed conclusion")
            require(task["reviews"] and task["reviews"][-1]["verdict"] == "pass", "review_missing", "Accepted task must retain its review")
            accepted.extend(criteria)
            evidence.extend(e for e in task["evidence"] if e["stage"] == result["stage"])
            conclusions.append({"task_id": key, **result})
        except ValueError as exc:
            missing.append({"task_id": key, "criteria": criteria, "reason": str(exc)})
    failed = {c for gap in missing for c in gap["criteria"]}
    accepted = sorted(set(accepted) - failed)
    recommendations = technical_debt(state)
    decisions = payload.get("recommendation_decisions")
    if decisions is None:
        decisions = [{"finding_id": f["finding_id"], "action": "defer",
                      "reason": "Await explicit user approval after plan completion"}
                     for f in recommendations]
    require(isinstance(decisions, list) and all(isinstance(d, dict) for d in decisions),
            "recommendation_decisions", "Decisions must be objects")
    require(len(decisions) == len(recommendations)
            and {d.get("finding_id") for d in decisions} == {f["finding_id"] for f in recommendations}
            and all(d.get("reason") and d.get("action") in {"defer", "reject"} for d in decisions),
            "recommendation_decisions", "Identify each finding; defer debt or record rejection. Fixes require explicit user approval as follow-up after completion")
    whole = {c for check in state.get("verification", {}).values() for c in check["criteria"]}
    state["final"] = {"head": head, "time": now(), "accepted_criteria": accepted,
        "missing": missing, "evidence": evidence, "verification_results": conclusions,
        "unassessed_criteria": sorted(whole - set(accepted)),
        "recommendations": recommendations, "decisions": decisions,
        "commits": {k: t["commits"] for k, t in state["tasks"].items()},
        "result": "partial" if missing else "complete"}
    state["status"] = "blocked" if missing else "completed"
    if missing:
        state["blockers"].append({"reason": "completion_incomplete", "resume_condition": "Accept remaining tasks or reconcile execution state", "missing": missing})
    return state["final"]
