"""Small read projection of verified state, not a transition authorization API."""
from .scheduler import available


def compact(state):
    # Called only after state.read has validated the complete persisted history.
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
    return {
        "view": "compact", "view_version": 1,
        **{key: state[key] for key in (
            "change_id", "run_id", "revision", "owner", "status", "mode",
            "updated_at", "blockers",
        )},
        "tasks": tasks, "active_roles": roles,
        "available_tasks": available(state),
        "artifacts": {"state": "state.json", "run": f"runs/{state['run_id']}"},
    }
