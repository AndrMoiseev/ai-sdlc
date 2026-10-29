"""Final acceptance requires fresh independent checks of every AC at final HEAD."""
from .repository import repository
from .common import now, require
from .commits import confirm, index_tree
from .verification import valid_evidence
from .review_policy import technical_debt
from .verification_results import applicable as conclusion


def conclusion_gaps(state, task, directory, required):
    try:
        result = conclusion(state, task, directory, "final")
        return [{"criteria": [item["criterion_id"]], "reason": "verification_" + item["outcome"],
                 "code": "verification_" + item["outcome"],
                 "detail": item["reason"], "verification_result": result["id"]}
                for item in result["criteria_results"] if item["outcome"] != "passed"]
    except ValueError as exc:
        return [{"criteria": sorted(required), "reason": str(exc), "code": getattr(exc, "code", None)}]


def refactoring_result(state, directory):
    from . import final_checks
    missing = [{"reason": blocker["reason"], "criteria": [], "task_id": blocker.get("task_id")} for blocker in state["blockers"]]
    accepted, evidence, current = [], [], None
    retired = final_checks.retired(state)
    try:
        final_checks.ready(state)
        current, evidence, gaps = final_checks.evidence(state, directory)
        missing.extend(gaps)
        covered = {criterion for check in current["checks"] for criterion in check["criteria"]}
        required = final_checks.required_criteria(state)
        missing.extend(conclusion_gaps(state, None, directory, required))
        for ident in sorted(required - covered):
            missing.append({"criteria": [ident], "reason": "criteria_uncovered"})
        failed = {criterion for gap in missing for criterion in gap["criteria"]}
        passed = {criterion for item in evidence for criterion in item["criteria"]}
        accepted = sorted(required & passed - failed)
    except ValueError as exc:
        missing.append({"criteria": sorted(final_checks.criteria(state)), "reason": str(exc)})
    return accepted, evidence, missing, {"basis": current, "retired_checks": retired,
        "accepted_tasks": [key for key, task in state["tasks"].items() if task["status"] == "accepted"],
        "whole_criteria": sorted(final_checks.criteria(state))}


def finalize(state, payload, directory):
    root = state["basis"]["project_root"]
    head = repository(root).head()
    missing, accepted, evidence = [{"reason": b["reason"], "criteria": [], "task_id": b.get("task_id")} for b in state["blockers"]], [], []
    extra = {}
    is_refactoring = state["basis"].get("work_kind") == "refactoring"
    if is_refactoring:
        accepted, evidence, missing, extra = refactoring_result(state, directory)
    for key, task in (() if is_refactoring else state["tasks"].items()):
        if task["status"] != "accepted" or not task["commits"]:
            missing.append({"task_id": key, "criteria": task["plan"]["covers"], "reason": "task_not_accepted"})
            continue
        try:
            for commit in task["commits"]:
                confirm(state, task, commit)
            require(index_tree(root, task["paths"], head) == repository(root).tree("HEAD"), "uncommitted_result", "Task files differ from final HEAD")
            checks = valid_evidence(state, task, directory, "final")
            require(all(e.get("head") == head for e in checks), "final_head", "Final evidence must name current HEAD")
            evidence.extend(checks)
            gaps = conclusion_gaps(state, task, directory, task["plan"]["covers"])
            missing.extend({**gap, "task_id": key} for gap in gaps)
            failed = {criterion for gap in gaps for criterion in gap["criteria"]}
            accepted.extend(criterion for criterion in task["plan"]["covers"] if criterion not in failed)
        except ValueError as exc:
            missing.append({"task_id": key, "criteria": task["plan"]["covers"], "reason": str(exc)})
    if not is_refactoring and state.get("final_checks"):
        from . import final_checks
        current = None
        project_evidence, gaps = [], []
        required = sorted({criterion for check in final_checks.registry(state)["checks"] for criterion in check["criteria"]})
        try:
            final_checks.ready(state)
            current, project_evidence, gaps = final_checks.evidence(state, directory)
            gaps.extend(conclusion_gaps(state, None, directory, required))
        except ValueError as exc:
            gaps = [{"criteria": required, "reason": str(exc)}]
        missing.extend(gaps)
        evidence.extend(project_evidence)
        extra["project_checks"] = {"basis": current, "criteria": required, "gaps": gaps}
    if not is_refactoring:
        # A shared criterion needs every applicable task and project obligation.
        failed = {criterion for gap in missing for criterion in gap["criteria"]}
        accepted = [criterion for criterion in accepted if criterion not in failed]
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
    conclusions = []
    for task_id, holder in [*state["tasks"].items(), (None, state.get("final_checks", {}))]:
        latest = next((item for item in reversed(holder.get("verification_results", [])) if item["stage"] == "final"), None)
        if latest is not None:
            conclusions.append({"task_id": task_id, **latest})
    for gap in missing:
        gap.setdefault("next_action", "Obtain current complete final execution and conclusion; attribute defects to an owned repair before edits")
    state["final"] = {"head": head, "time": now(), "accepted_criteria": sorted(set(accepted)), "missing": missing, "evidence": evidence, "verification_results": conclusions, "recommendations": recommendations, "decisions": decisions, "commits": {k: t["commits"] for k, t in state["tasks"].items()}, "result": "partial" if missing else "complete", **extra}
    state["status"] = "blocked" if missing else "completed"
    if missing:
        state["blockers"].append({"reason": "final_incomplete", "resume_condition": "Resolve final missing evidence or defects", "missing": missing})
    return state["final"]
