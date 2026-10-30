"""Bound existing role assignments to current source and complete check registries."""
from copy import deepcopy
from datetime import datetime
import math
import time
from pathlib import PurePosixPath

from .common import digest, require
from .inputs import spec_modules, document_paths
from .state import snapshot

execution_kind = spec_modules("check_kinds").execution_kind
STAGES = {"baseline", "self", "independent", "integration"}


def basis(state, task, kind="research", stage=None):
    from .verification import root_for
    require(task is not None or kind == "research", "assignment_scope", "Checks require a task scope")
    source = snapshot(state, root_for(state, task) if task else None)
    result = {"run_id": state["run_id"], "change_id": state["change_id"], "source": source,
              "manifest": digest({"head": state["basis"]["head"], "document_paths": document_paths(state["basis"])})}
    if kind == "checks":
        from .check_registry import selected
        result.update(registry_revision=task.get("check_registry", {}).get("revision", 0),
                      checks=deepcopy(selected(state, task)))
    return result


def validate(state, task, role):
    assignment = role.get("assignment")
    spec_modules("explorer").validate_assignment(assignment)
    require(assignment["id"] == role["role_id"], "assignment_id", "Assignment ID is the registered role ID")
    require(assignment["scope"] == {"project": state["basis"]["project_root"], "work": state["change_id"],
                                    "task": task["plan"]["id"] if task else None},
            "assignment_scope", "Assignment must name this project, work and task scope")
    kind, stage = assignment["kind"], assignment.get("stage")
    if kind == "checks":
        require(stage in STAGES and task is not None, "assignment_stage", "Use an applicable task stage")
    current = basis(state, task, kind, stage)
    require(assignment["basis"] == current, "assignment_basis", "Assignment requires the current source, manifest and registry")
    if kind == "checks":
        require(assignment["check_ids"] == [check["id"] for check in current["checks"]]
                and assignment["registry_revision"] == current["registry_revision"],
                "assignment_checks", "Assign the complete exact check set and registry revision")
    observations = role["capabilities"].get("observations")
    observed = spec_modules("explorer").check_capabilities(assignment, observations)
    require(observed["ready"], "host_limits", "Explorer capability unavailable: " + str(observed["unavailable"]))
    return assignment


def authorize(state, task, role_id, stage, active=True, current_basis=True):
    role = state["roles"].get(role_id)
    require(role and role["kind"] == "explorer" and role["task_id"] == (task["plan"]["id"] if task else None)
            and role["status"] in ({"active"} if active else {"active", "finished"}),
            "role_unavailable", "Active independent explorer with matching scope required")
    assignment = role.get("assignment", {})
    require(assignment.get("kind") == "checks" and assignment.get("stage") == stage,
            "assignment_stage", "Explorer must hold a checks assignment for this exact stage")
    if current_basis:
        validate(state, task, role)
    return role


def procedure_role(state, task, role_id, stage, check, active=True, current_basis=True):
    kind = execution_kind(check)
    if kind == "deterministic":
        return authorize(state, task, role_id, stage, active=active, current_basis=current_basis)
    role = state["roles"].get(role_id)
    expected = "verifier"
    require(role and role["kind"] == expected and role["task_id"] == (task["plan"]["id"] if task else None)
            and role["status"] in ({"active"} if active else {"active", "finished"}),
            "procedure_role", "Semantic procedures require their independent task verifier")
    return role


def research_result(result):
    require(isinstance(result, dict) and result.get("kind") == "research"
            and isinstance(result.get("answer"), str) and result["answer"].strip(),
            "research_result", "Research result requires kind and answer")
    for field in ("references", "inspected_scope", "limitations", "assumptions", "questions"):
        require(isinstance(result.get(field), list), "research_result", "Research result requires " + field)
    require(result["inspected_scope"], "research_result", "Record the inspected scope")


class Deadline:
    """Persist wall-clock bounds between events; use monotonic time inside an event."""
    def __init__(self, role, timeout, previous=None):
        require(isinstance(timeout, (float, int)) and not isinstance(timeout, bool)
                and math.isfinite(timeout) and timeout > 0, "check_timeout", "Use a positive finite batch timeout")
        limits = role["assignment"]["limits"]
        maximum = limits.get("timeout", timeout)
        require(isinstance(maximum, (float, int)) and not isinstance(maximum, bool)
                and math.isfinite(maximum) and maximum > 0, "check_timeout", "Assignment timeout must be positive and finite")
        observed = time.time()
        started = previous["started"] if previous else observed
        expires = started + min(timeout, maximum)
        if previous:
            expires = min(expires, previous["expires"])
        if limits.get("deadline") is not None:
            require(isinstance(limits["deadline"], str), "check_timeout", "Absolute deadline must be ISO-8601 text")
            try:
                absolute = datetime.fromisoformat(limits["deadline"].replace("Z", "+00:00"))
                require(absolute.tzinfo is not None, "check_timeout", "Absolute deadline requires a timezone")
                expires = min(expires, absolute.timestamp())
            except (TypeError, ValueError) as exc:
                raise ValueError("check_timeout: Invalid absolute deadline") from exc
        self.record = {"started": started, "expires": expires}
        self.end = time.monotonic() + max(0, expires - observed)

    def remaining(self):
        return max(0, self.end - time.monotonic())


def attempt_deadline(state, task, role, timeout=300):
    """Continue the existing assigned attempt, including a replacement explorer."""
    cycles = ({task["plan"]["id"]: task.get("test_repair_cycles_started", 0)} if task else
              {ident: value.get("test_repair_cycles_started", 0) for ident, value in state["tasks"].items()})
    assignment = role["assignment"]
    prior = [other["check_budget"] for other in state["roles"].values()
             if other.get("check_budget", {}).get("repair_cycles") == cycles
             and all(other.get("assignment", {}).get(key) == assignment.get(key)
                     for key in ("scope", "stage", "basis"))]
    previous = min(prior, key=lambda item: item["expires"]) if prior else None
    deadline = Deadline(role, timeout, previous)
    role["check_budget"] = {**deadline.record, "repair_cycles": cycles}
    return deadline


def procedure_budget(state, task, role, check, timeout=300):
    if execution_kind(check) != "deterministic":
        return {}
    deadline = attempt_deadline(state, task, role, timeout)
    require(deadline.remaining() > 0, "check_deadline", "The assigned check attempt deadline expired")
    return {"check_deadline": deadline.record, "remaining_timeout": deadline.remaining()}


def procedure_outcome(pending, reported, unchanged):
    if not unchanged:
        return "stale"
    if pending.get("check_deadline", {}).get("expires", math.inf) <= time.time():
        return "unavailable"
    return reported


def expired(check):
    return {"check_id": check["id"], "outcome": "unavailable", "exit_code": None,
            "limitation": "check_deadline", "description": "The full check set deadline expired; command not started"}
