"""Task-lifetime budgets survive retries, integration and session changes."""
from .common import require


def block(state, task, reason):
    item = {"reason": reason, "task_id": task["plan"]["id"], "resume_condition": "Explicit finite user budget extension"}
    if item not in state["blockers"]:
        state["blockers"].append(item)
    state["status"] = "blocked"


def reserve_review(state, task, round_id):
    require(task["active_review"] is None, "review_active", "Resume the existing review instead of reserving twice")
    if task["review_rounds_started"] >= task["review_limit"]:
        block(state, task, "review_limit_reached")
        return False
    task["review_rounds_started"] += 1
    task["active_review"] = round_id
    return True


def failure(state, task, budget, outcome):
    task["failure"] = {"budget": budget, "outcome": outcome}
    if budget == "review" and task["review_rounds_started"] >= task["review_limit"]:
        block(state, task, "review_limit_reached")
    if budget == "test" and task["test_repair_cycles_started"] >= task["test_repair_limit"] and not task["active_repair"]:
        block(state, task, "test_repair_limit_reached")
    if outcome == "unavailable":
        item = {"reason": "required_check_unavailable", "task_id": task["plan"]["id"], "resume_condition": "Restore required runner"}
        if item not in state["blockers"]:
            state["blockers"].append(item)
        state["status"] = "blocked"


def repair(state, task, p):
    require(task and task["status"] != "pending" and p.get("reason"), "repair_reason", "Repair requires a started task and reason")
    require(task.get("failure") or p.get("defect_evidence"), "repair_evidence", "Provide reproducible defect evidence")
    if task["review_rounds_started"] >= task["review_limit"]:
        block(state, task, "review_limit_reached")
        return {"blocked": "review_limit_reached"}
    if task.get("last_check_failed") or p.get("test_failure"):
        require(not task["active_repair"], "repair_active", "Resume existing repair cycle")
        if task["test_repair_cycles_started"] >= task["test_repair_limit"]:
            block(state, task, "test_repair_limit_reached")
            return {"blocked": "test_repair_limit_reached"}
        task["test_repair_cycles_started"] += 1
        task["active_repair"] = f"cycle-{task['test_repair_cycles_started']}"
    role = state["roles"].get(p.get("executor", task.get("executor")))
    require(role and role["kind"] == "executor" and role["task_id"] == task["plan"]["id"] and role["status"] in {"active", "finished"}, "executor_missing", "Use the available assigned author or registered successor")
    role["status"] = "active"
    task["executor"] = role["role_id"]
    from .state import snapshot
    from .verification import root_for
    if task["status"] == "accepted":
        task["start_snapshot"] = snapshot(state, root_for(state, task))
        task.pop("freeze_base", None)
    task["candidate"] = None
    task["status"] = "repairing"
    affected = {task["plan"]["id"]}
    while True:
        more = {key for key, value in state["tasks"].items() if set(value["plan"]["depends_on"]) & affected} - affected
        if not more:
            break
        affected.update(more)
    for key, other in state["tasks"].items():
        if key != task["plan"]["id"] and key in affected and other["status"] == "accepted":
            other["before_block"] = "accepted"
            other["status"] = "blocked"
            other["blockers"].append({"reason": "predecessor_changed", "resume_condition": "Reverify dependency"})
    return {"status": "repairing", "cycle": task["active_repair"]}


def extend(state, task, p):
    require(task and p.get("budget") in {"review", "test"} and p.get("source") and p.get("text"), "budget_decision", "Explicit user decision and source required")
    field = "review_limit" if p["budget"] == "review" else "test_repair_limit"
    require(type(p.get("limit")) is int and task[field] < p["limit"] < 1000000, "finite_limit", "New limit must be a larger finite integer")
    task[field] = p["limit"]
    task["budget_decisions"].append(p)
    reason = "review_limit_reached" if p["budget"] == "review" else "test_repair_limit_reached"
    state["blockers"] = [b for b in state["blockers"] if not (b["reason"] == reason and b.get("task_id") == task["plan"]["id"])]
    state["status"] = "blocked" if state["blockers"] else "active"
    return {"limit": task[field], "status": state["status"]}
