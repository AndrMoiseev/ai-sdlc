"""Approved registry revisions, with confirmation atomic with task acceptance."""
from copy import deepcopy

from .common import require


def refactoring(state):
    return state["basis"].get("work_kind", "change") == "refactoring"


def confirmed_revision(task):
    registry = task.get("check_registry", {})
    # Only old registries, which cannot contain staged transitions, need the
    # accepted-task compatibility rule. New registries track confirmation explicitly.
    legacy = registry.get("revision", 0) if task["status"] == "accepted" and not registry.get("transition") else 0
    return registry.get("confirmed_revision", legacy)


def validate(task):
    registry = task["check_registry"]
    confirmed = confirmed_revision(task)
    require(type(confirmed) is int and 0 <= confirmed <= registry["revision"],
            "registry_changed", "Invalid confirmed registry revision")
    require(registry.get("transition") == registry["history"][-1].get("transition"),
            "registry_changed", "Registry transition differs from its immutable snapshot")


def overlay(checks, transition):
    before = {check["id"]: check for check in transition["before"]}
    after = {check["id"]: check for check in transition["after"]}
    for ident in before.keys() - after.keys():
        checks.pop(ident, None)
    for ident, check in after.items():
        if before.get(ident) != check:
            checks[ident] = check


def confirmed_tasks(state):
    """Order confirmations by committed revision without expanding full history."""
    from .state_history import entries, lookup
    tasks = [task for task in state["tasks"].values() if confirmed_revision(task)]
    accepted = {}
    for task in tasks:
        ident = task["plan"]["id"]
        event_id = task["check_registry"].get("confirmation_event")
        if event_id:
            entry = lookup(state.objects, state["event_index"], event_id)
        else:
            # Registries written before confirmation IDs were recorded.
            entry = next((item for item in entries(state.objects, state)
                          if item["event"]["type"] == "accept" and item["event"]["task_id"] == ident), None)
        require(entry and entry["event"]["type"] == "accept" and entry["event"]["task_id"] == ident,
                "registry_confirmation_missing", "Confirmed registry requires its recorded acceptance event")
        accepted[ident] = entry["revision"]
    return sorted(tasks, key=lambda task: accepted[task["plan"]["id"]])


def require_new_ids(state, task, checks):
    """Ordinary insertion cannot acquire another task's check identity."""
    if not refactoring(state):
        return
    reserved = set()
    reserved.update(state.get("verification", {}))
    reserved.update(check["id"] for check in state.get("final_checks", {}).get("checks", []))
    for other in state["tasks"].values():
        if other["plan"]["id"] == task["plan"]["id"]:
            continue
        reserved.update(other["plan"]["id"] + "/" + item["id"] for item in other["plan"]["verification"])
        reserved.update(item["id"] for item in other["checks"])
        # Retired identities stay reserved, preventing accidental resurrection.
        for entry in other.get("check_registry", {}).get("history", []):
            reserved.update(item["id"] for item in entry["checks"])
    require(not any(check.get("id") in reserved for check in checks), "duplicate_check",
            "Check ID belongs to another task; use an authorized registry revision to change its obligation")


def selected(state, task, final=False):
    """Keep confirmed obligations; overlay only this candidate's pending revision."""
    if not refactoring(state):
        return task["checks"]
    from .verification import registry_current
    checks = {}
    for previous in confirmed_tasks(state):
        revision = confirmed_revision(previous)
        registry_current(state, previous)
        history = previous["check_registry"]["history"]
        checks.update((check["id"], check) for check in history[revision - 1]["checks"])
        for entry in history[:revision]:
            if entry.get("transition"):
                overlay(checks, entry["transition"])
    if not final:
        checks.update((check["id"], check) for check in task["checks"])
        for entry in task["check_registry"]["history"]:
            if entry.get("transition"):
                overlay(checks, entry["transition"])
        # The target may be an earlier accepted task. Its historical local checks
        # must not restore a boundary retired by a later confirmed transition.
        if task["status"] == "accepted":
            return selected(state, task, final=True)
    return list(checks.values())


def evidence_basis(state, task, final=False):
    result = {"revision": task["check_registry"]["revision"], "checks": selected(state, task, final)}
    # Confirmation alone leaves the accepting candidate unchanged. Other tasks'
    # confirmed revisions still invalidate it when applicability changes.
    return result


def strings(value):
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value))


def authorized(state, task, payload, before, after):
    basis = payload.get("basis", {})
    require(isinstance(basis, dict) and basis and set(basis) <= {"test_changes", "transitional_criteria"}
            and all(strings(value) for value in basis.values()) and any(basis.values()),
            "revision_basis", "Name approved test_changes or transitional acceptance criteria")
    changes = {item["id"]: item for item in task["plan"].get("test_changes", [])}
    require(set(basis.get("test_changes", [])) <= changes.keys(), "revision_basis", "Unknown task test-change permission")
    changes = [changes[ident] for ident in basis.get("test_changes", [])]
    transitions = []
    for ident in basis.get("transitional_criteria", []):
        criterion = state["acceptance"].get(ident, {})
        require(criterion.get("lifetime") == "transitional" and criterion.get("until_task") == task["plan"]["id"],
                "revision_basis", "Only the approved terminating task can retire a transitional criterion")
        transitions.append(criterion)
    permissions = set()
    replacements = set()
    for change in changes:
        permissions.update(change["criteria"])
        replacements.update(change.get("replacement_criteria", []))
    for criterion in transitions:
        permissions.add(criterion["id"])
        replacements.update(criterion["replaced_by"])
    old, new = {item["id"]: item for item in before}, {item["id"]: item for item in after}
    changed = {ident for ident in old.keys() | new.keys() if old.get(ident) != new.get(ident)}
    require(changed, "revision_unchanged", "New registry contents must differ")
    mapping = payload.get("mapping")
    require(isinstance(mapping, dict) and set(mapping) == changed
            and all(isinstance(value, str) and value.strip() for value in mapping.values()),
            "revision_mapping", "Map every changed check to its approved group and actual affected tests")
    affected = {criterion for ident in changed for item in (old.get(ident), new.get(ident)) if item for criterion in item["criteria"]}
    require(affected <= permissions | replacements, "revision_scope", "Changed check exceeds the approved group or transition")
    for ident in changed:
        prior, following = old.get(ident), new.get(ident)
        if prior:
            require(any(set(prior["criteria"]) <= set(change["criteria"]) and change["action"] in {"adapt", "move", "remove"}
                        for change in changes) or set(prior["criteria"]) <= {item["id"] for item in transitions},
                    "revision_scope", "Adding a check does not authorize removing or adapting an existing check")
        if following:
            require(any(set(following["criteria"]) <= set(change["criteria"]) | set(change.get("replacement_criteria", []))
                        for change in changes) or set(following["criteria"]) <= replacements,
                    "revision_scope", "Replacement check needs an approved criterion")
    covered = {criterion for item in after for criterion in item["criteria"]}
    previous = {criterion for item in before for criterion in item["criteria"]}
    preserved = {criterion for item in state["tasks"].values() for criterion in item["plan"].get("preserves", [])}
    require(strings(payload.get("preserves")) and set(payload["preserves"]) == affected & preserved,
            "revision_preservation", "Name the exact preserved obligations affected by this revision")
    require(previous & preserved <= covered and replacements <= covered,
            "criteria_uncovered", "Preservation and replacing-state checks remain mandatory")
    retired = {item["id"] for item in transitions}
    structural = {criterion for change in changes if change["action"] == "remove" and change.get("decision")
                  for criterion in change["criteria"] if criterion not in preserved}
    require(previous - covered <= retired | structural, "criteria_uncovered", "A persistent obligation keeps its identity when its test moves")
    # An architecture decision permits retiring a structural constraint, never a
    # project check merely sharing the criterion of a temporary adapter.
    for ident in old.keys() - new.keys():
        require(old[ident]["source"] == "tasks.md" or changes,
                "revision_scope", "Project checks require an explicit approved test-change group")


def revise(state, task, event):
    from .verification import local_criteria, record_registry, registry_current, require_command
    require(refactoring(state), "revision_work_kind", "Registry revisions are for approved refactoring work")
    require(task["status"] in {"running", "repairing"} and task.get("baseline_checks"),
            "revision_phase", "Capture baseline; revise within the running or reserved repair task")
    require(not task.get("last_check_failed") or task["active_repair"], "repair_cycle_required", "Reserve repair before revising a failed set")
    executor = state["roles"].get(task.get("executor"), {})
    require(executor.get("status") == "active", "writer_active", "Assigned executor must own the revision")
    registry_current(state, task)
    payload = event["payload"]
    require(type(payload.get("registry_revision")) is int and payload["registry_revision"] == task["check_registry"]["revision"],
            "registry_revision_conflict", "Re-read the current registry revision")
    before = selected(state, task)
    require(payload.get("before") == before, "registry_revision_conflict", "Exact previous applicable check records required")
    after = payload.get("after")
    require(isinstance(after, list) and after and all(isinstance(item, dict) for item in after), "check_schema", "Exact new check records required")
    allowed = local_criteria(state, task) | {criterion for item in before for criterion in item["criteria"]}
    old = {item["id"]: item for item in before}
    for check in after:
        require(set(check) <= {"id", "criteria", "source", "location", "run", "cwd", "configuration", "setup"}
                and {"id", "criteria", "source", "run", "cwd", "configuration", "setup"} <= check.keys()
                and isinstance(check["id"], str) and check["id"] and isinstance(check["source"], str) and check["source"]
                and strings(check["criteria"]) and check["criteria"] and set(check["criteria"]) <= allowed
                and isinstance(check["cwd"], str) and isinstance(check["configuration"], dict),
                "check_schema", "New checks require complete scoped command records")
        if old.get(check["id"]) == check:
            continue
        require(check["setup"] is None and isinstance(check["run"], dict) and set(check["run"]) in ({"command"}, {"procedure"}),
                "check_schema", "A replacement requires an exact command or an existing procedure")
        if "command" in check["run"]:
            require_command(check["run"]["command"])
        else:
            require(isinstance(check["run"]["procedure"], str) and check["run"]["procedure"].strip(), "check_schema", "Procedure path required")
        from .common import contained
        from .verification import root_for
        root = root_for(state, task)
        if check["cwd"] != ".":
            contained(root, check["cwd"])
        if "location" in check:
            from .inputs import spec_modules, basis_dependency
            spec_modules(basis_dependency(state["basis"]), "paths").verification_location(root, check["location"])
    require(len({check["id"] for check in after}) == len(after), "duplicate_check", "Duplicate revised check ID")
    require_new_ids(state, task, [check for check in after if check["id"] not in old])
    require(isinstance(payload.get("reason"), str) and payload["reason"].strip(), "revision_basis", "Record the reason for changed applicability")
    authorized(state, task, payload, before, after)
    own = {item["id"] for item in task["checks"]}
    task["checks"] = deepcopy([item for item in after if item["id"] in own or old.get(item["id"]) != item])
    task["check_registry"]["transition"] = {"event_id": event["event_id"], **deepcopy(payload)}
    record_registry(state, task, event)
    registry_current(state, task)
    task["candidate"] = None
    state["final"] = None
    return {"registry_revision": task["check_registry"]["revision"], "status": "pending_confirmation",
            "checks": selected(state, task)}


def confirm(state, task, event):
    if refactoring(state):
        task["check_registry"]["confirmed_revision"] = task["check_registry"]["revision"]
        task["check_registry"]["confirmation_event"] = event["event_id"]


def recovery(state):
    """Return two separate views; an interrupted revision is never auto-confirmed."""
    if not refactoring(state):
        return {}
    from .verification import registry_current
    result = {}
    for ident, task in state["tasks"].items():
        if not task.get("check_registry"):
            continue
        registry_current(state, task)
        registry = task["check_registry"]
        confirmed = confirmed_revision(task)
        pending = registry.get("transition")
        result[ident] = {"revision": registry["revision"], "confirmed_revision": confirmed,
                        "confirmed_checks": deepcopy(registry["history"][confirmed - 1]["checks"]) if confirmed else [],
                        "pending_transition": deepcopy(pending) if pending and registry["revision"] > confirmed else None}
    return result
