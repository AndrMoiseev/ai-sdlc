"""Admission by accepted dependencies, execution mode and resource conflicts."""
def available(state):
    if state["status"] != "active" or state["blockers"]:
        return []
    active = {k: t for k, t in state["tasks"].items() if t["status"] not in {"pending", "accepted"}}
    if state["mode"] == "sequential" and active:
        return []
    accepted = {k for k, t in state["tasks"].items() if t["status"] == "accepted"}
    result = []
    for key, task in sorted(state["tasks"].items(), key=lambda pair: pair[1]["plan"]["number"]):
        if task["status"] != "pending" or not set(task["plan"]["depends_on"]) <= accepted:
            continue
        conflicts = set(task["plan"].get("cannot_parallel_with", []))
        if conflicts & active.keys() or any(key in t["plan"].get("cannot_parallel_with", []) for t in active.values()):
            continue
        result.append(key)
    return result[:1] if state["mode"] == "sequential" else result
