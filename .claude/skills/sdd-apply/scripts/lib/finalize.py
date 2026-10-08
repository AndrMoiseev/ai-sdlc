"""Final acceptance requires fresh independent checks of every AC at final HEAD."""
from .common import git, now, require
from .commits import confirm, index_tree
from .verification import valid_evidence


def finalize(state, payload, directory):
    root = state["basis"]["project_root"]
    head = git(root, "rev-parse", "HEAD")
    missing, accepted, evidence = [{"reason": b["reason"], "criteria": [], "task_id": b.get("task_id")} for b in state["blockers"]], [], []
    for key, task in state["tasks"].items():
        if task["status"] != "accepted" or not task["commits"]:
            missing.append({"task_id": key, "criteria": task["plan"]["covers"], "reason": "task_not_accepted"})
            continue
        try:
            for commit in task["commits"]:
                confirm(state, task, commit)
            require(index_tree(root, task["paths"], head) == git(root, "rev-parse", "HEAD^{tree}"), "uncommitted_result", "Task files differ from final HEAD")
            checks = valid_evidence(state, task, directory, "final")
            require(all(e.get("head") == head for e in checks), "final_head", "Final evidence must name current HEAD")
            evidence.extend(checks)
            accepted.extend(task["plan"]["covers"])
        except ValueError as exc:
            missing.append({"task_id": key, "criteria": task["plan"]["covers"], "reason": str(exc)})
    recommendations = [f for t in state["tasks"].values() for r in t["reviews"] for f in r["findings"] if f["severity"] == "recommendation"]
    decisions = payload.get("recommendation_decisions", [])
    if recommendations and (len(decisions) != len(recommendations) or not all(d.get("reason") and d.get("action") in {"fix", "defer", "reject"} for d in decisions)):
        missing.append({"reason": "recommendation_decisions_required", "criteria": []})
    state["final"] = {"head": head, "time": now(), "accepted_criteria": sorted(set(accepted)), "missing": missing, "evidence": evidence, "recommendations": recommendations, "decisions": decisions, "commits": {k: t["commits"] for k, t in state["tasks"].items()}, "result": "partial" if missing else "complete"}
    state["status"] = "blocked" if missing else "completed"
    if missing:
        state["blockers"].append({"reason": "final_incomplete", "resume_condition": "Resolve final missing evidence or defects", "missing": missing})
    return state["final"]
