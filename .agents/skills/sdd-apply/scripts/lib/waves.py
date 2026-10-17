"""Derived execution waves. Grouping never changes scheduler admission."""
from .scheduler import available


LABELS = {"completed": "Completed", "in_progress": "In progress", "ready": "Ready to launch",
          "waiting_dependencies": "Waiting for dependencies", "waiting": "Waiting to launch"}


def incompatible(left, right):
    return (right["id"] in left.get("cannot_parallel_with", [])
            or left["id"] in right.get("cannot_parallel_with", []))


def planned_waves(state):
    """Stable for a fixed plan and mode, including across acceptance and retries."""
    plans = {key: task["plan"] for key, task in state["tasks"].items()}
    remaining, ordered, seen = set(plans), [], set()
    while remaining:
        ready = sorted((key for key in remaining if set(plans[key]["depends_on"]) <= seen),
                       key=lambda key: plans[key]["number"])
        if not ready:
            raise ValueError("wave_dependencies: cyclic or missing task dependency")
        # Pick one at a time: sequential mode follows the scheduler's number priority.
        key = ready[0]
        ordered.append(key)
        seen.add(key)
        remaining.remove(key)
    groups = []
    for key in ordered:
        deps = set(plans[key]["depends_on"])
        group = next((g for g in groups if state["mode"] == "parallel"
                      and set(g["depends_on"]) == deps
                      and all(not incompatible(plans[key], plans[other]) for other in g["tasks"])), None)
        if group is None:
            group = {"id": f"wave-{len(groups) + 1}", "number": len(groups) + 1,
                     "depends_on": sorted(deps, key=lambda dep: plans[dep]["number"]), "tasks": []}
            groups.append(group)
        group["tasks"].append(key)
    return groups


def waiting_reasons(state, key, candidates):
    tasks, task = state["tasks"], state["tasks"][key]
    if task["status"] != "pending":
        return []
    reasons = []
    if state["status"] != "active" or state["blockers"]:
        reasons.append({"kind": "run", "tasks": []})
    deps = [dep for dep in task["plan"]["depends_on"] if tasks[dep]["status"] != "accepted"]
    if deps:
        reasons.append({"kind": "dependencies", "tasks": deps})
    active = {k: t for k, t in tasks.items() if k != key and t["status"] not in {"pending", "accepted"}}
    if state["mode"] == "sequential":
        if active:
            reasons.append({"kind": "sequential", "tasks": list(active)})
        elif not reasons and key not in candidates:
            reasons.append({"kind": "sequential", "tasks": candidates})
    conflicts = [k for k, other in active.items() if incompatible(task["plan"], other["plan"])]
    if conflicts:
        reasons.append({"kind": "conflict", "tasks": conflicts})
    paths = {path.casefold() for path in task.get("paths", [])}
    resources = set((task.get("worktree") or {}).get("resources", []))
    for kind, occupied in (
        ("files", [k for k, other in active.items() if paths & {p.casefold() for p in other.get("paths", [])}]),
        ("resources", [k for k, other in tasks.items() if k != key and other["status"] != "accepted"
                       and resources & set((other.get("worktree") or {}).get("resources", []))]),
    ):
        if occupied:
            reasons.append({"kind": kind, "tasks": occupied})
    return reasons


def waiting_text(reasons):
    prefixes = {"run": "Execution paused; see blockers", "dependencies": "Waiting for acceptance",
                "sequential": "Sequential mode; waiting for", "conflict": "Cannot run alongside",
                "files": "Shared files occupied by", "resources": "Shared resources occupied by"}
    return [prefixes[r["kind"]] + (": " + ", ".join(r["tasks"]) if r["tasks"] else "") for r in reasons]


def projection(state):
    waves = planned_waves(state)
    candidates = available(state)
    waiting = {key: waiting_reasons(state, key, candidates) for key in state["tasks"]}
    for wave in waves:
        members = [state["tasks"][key] for key in wave["tasks"]]
        wave["accepted"] = sum(t["status"] == "accepted" for t in members)
        wave["blocked"] = [key for key in wave["tasks"] if state["tasks"][key]["status"] == "blocked"
                           or state["tasks"][key]["blockers"]]
        if wave["accepted"] == len(members):
            status = "completed"
        elif any(t["status"] not in {"pending", "accepted", "blocked"} for t in members):
            status = "in_progress"
        elif any(state["tasks"][dep]["status"] != "accepted" for dep in wave["depends_on"]):
            status = "waiting_dependencies"
        elif any(key in candidates and not waiting[key] for key in wave["tasks"]):
            status = "ready"
        else:
            status = "waiting"
        wave.update(status=status, label=LABELS[status])
    return waves, waiting
