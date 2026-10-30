"""Read and reconcile legacy whole-check metadata; no execution stage remains."""
from copy import deepcopy
from .common import require
from .check_registry import refactoring
from .inputs import read_plan_document, document_paths


def criteria(state):
    if not refactoring(state):
        allowed = {ident for task in state["tasks"].values() for ident in task["plan"]["covers"]}
        records = [record for entry in document_paths(state["basis"])
                   if entry.startswith("specs/") and entry.endswith("/spec.md")
                   for record in read_plan_document(state["basis"], entry)
                   if record["sdd_record"] == "acceptance" and record["id"] in allowed]
        require({record["id"] for record in records} == allowed, "criteria_uncovered", "Every covers criterion needs its approved specification")
        return {record["id"]: record for record in records}
    return {record["id"]: record for record in read_plan_document(state["basis"], "design.md") if record["sdd_record"] == "criterion"}


def registry(state):
    result = state.get("final_checks")
    require(result and result["history"] and result["revision"] == len(result["history"])
            and result["history"][-1]["checks"] == result["checks"],
            "final_registry_missing", "Register whole-result checks without a task owner")
    return result


def record_revision(result, event):
    result["revision"] += 1
    result["history"].append({"revision": result["revision"], "event_id": event["event_id"],
                              "checks": deepcopy(result["checks"])})


def planned_checks(records):
    return [{"id": item["id"], "criteria": item["criteria"], "source": "tasks.md",
             "location": item["location"], "run": item["run"], "setup_task": item.get("setup_task"),
             "setup": None, "cwd": ".", "configuration": {},
             **({"execution_kind": item["execution_kind"]} if "execution_kind" in item else {})}
            for item in records]


def revised_registry(state, approved, event):
    """Apply the approved whole definitions while retaining project obligations."""
    if not state.get("final_checks"):
        return None
    result = deepcopy(registry(state))
    if approved.get("work_kind") != "refactoring":
        return result
    previous = {item["id"]: item for item in planned_checks(state.get("verification", {}).values())}
    following = planned_checks(approved["verification"])
    current = {item["id"]: item for item in result["checks"]}
    additional = [item for item in result["checks"] if item["id"] not in previous]
    require(not {item["id"] for item in following} & {item["id"] for item in additional},
            "duplicate_check", "Approved whole check ID conflicts with a registered project obligation")
    reserved = set()
    for task in state["tasks"].values():
        reserved.update(item["id"] for item in task["checks"])
        for entry in task.get("check_registry", {}).get("history", []):
            reserved.update(item["id"] for item in entry["checks"])
            for field in ("before", "after"):
                reserved.update(item["id"] for item in entry.get("transition", {}).get(field, []))
    for task in approved["tasks"]:
        reserved.update(task["id"] + "/" + item["id"] for item in task["verification"])
    require(not reserved & {item["id"] for item in following}, "duplicate_check",
            "Approved whole check ID conflicts with a task registry or transition")
    # Identical definitions keep their prepared setup. Changed definitions require
    # their newly approved run; old prepared commands remain in immutable history.
    checks = [deepcopy(current[item["id"]]) if previous.get(item["id"]) == item and item["id"] in current
              else deepcopy(item) for item in following] + additional
    if checks != result["checks"]:
        result["checks"] = checks
        record_revision(result, event)
        result["history"][-1]["basis_commit"] = approved["head"]
    return result
