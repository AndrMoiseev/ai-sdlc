"""Small read projection of verified state, not a transition authorization API."""
from .scheduler import available


def compact(state):
    # Current manifest and accessed objects are verified; audit checks history.
    tasks = {}
    for key, task in state["tasks"].items():
        tasks[key] = {field: task[field] for field in (
            "status", "attempt", "blockers", "review_limit",
            "review_rounds_started", "review_rounds_completed", "active_review",
            "test_repair_limit", "test_repair_cycles_started", "active_repair",
        )}
    roles = {
        key: {field: role[field] for field in ("task_id", "kind", "context_id")}
        for key, role in state["roles"].items() if role["status"] == "active"
    }
    whole = {}
    if state["basis"].get("work_kind") == "refactoring":
        from .final_checks import progress
        whole = {"whole_result": progress(state)}
    elif state.get("final_checks"):
        from .final_checks import progress
        whole = {"final_project_checks": progress(state)}
    return {
        **whole,
        "view": "compact", "view_version": 1,
        **({"work_kind": state["work_kind"]} if "work_kind" in state else {}),
        **{key: state[key] for key in (
            "change_id", "run_id", "revision", "status",
            "updated_at", "blockers",
        )},
        "tasks": tasks, "active_roles": roles,
        "available_tasks": available(state),
        "artifacts": {"state": "state.json", "run": f"runs/{state['run_id']}"},
    }
