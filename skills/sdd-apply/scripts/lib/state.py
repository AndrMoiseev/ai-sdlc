"""Revisioned event store. Rejected transitions never replace the state file."""
from copy import deepcopy
import json
from pathlib import Path
import uuid
import re
from .common import contained, contained_paths, digest, now, require, source_snapshot, write_json

from .state_storage import storage
from .path_resolution import resolve
from .state_objects import StateObjects
from . import state_history

TASK_STATES = {"pending", "running", "verifying", "reviewing", "integrating", "repairing", "committing", "blocked", "accepted"}


def lock(directory):
    return storage(directory).lock()


def recover_lock(directory):
    return storage(directory).recover_lock()


def save(directory, state):
    storage(directory).save(StateObjects(directory).pack(state, root=True))


def seal(state):
    objects = StateObjects(execution_directory(state["basis"]))
    packed = objects.pack(state, root=True)
    state["integrity"] = digest({k: v for k, v in packed.items() if k != "integrity"})


def execution_directory(basis):
    kind = basis.get("work_kind", "change")
    require(kind in ("change", "refactoring"), "state_root", "Unsupported work kind")
    change = basis["change_id"]
    require(isinstance(change, str) and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", change) and len(change) <= 64,
            "state_root", "Invalid work identity")
    root = "changes" if kind == "change" else "refactoring"
    directory = contained(basis["project_root"], f"sdd/{root}/{change}/execution")
    require(directory.parent == resolve(basis["change_root"]), "state_root", "State is outside its registered execution root")
    return directory


def read(directory, view="full"):
    require(view in ("full", "compact"), "read_view", "Expected full or compact")
    packed = json.loads(storage(directory).read().decode("utf-8"))
    require(packed.get("schema_version") == 2, "state_version", "Expected execution state schema 2")
    require(packed.get("integrity") == digest({k: v for k, v in packed.items() if k != "integrity"}), "state_corrupt", "State integrity mismatch")
    state = StateObjects(directory).open(deepcopy(packed))
    state.manifest = packed
    require(state["change_id"] == state["basis"]["change_id"] and state.get("work_kind", "change") == state["basis"].get("work_kind", "change"), "state_root", "State work identity differs from its basis")
    expected_directory = execution_directory(state["basis"])
    require(resolve(directory) == expected_directory, "state_root", "State is outside its registered execution root")
    require(type(state["revision"]) is int and state["revision"] >= 0, "history_corrupt", "Invalid revision")
    if state["revision"]:
        head = state.objects.get(state["event_head"])
        require(head["revision"] == state["revision"] and state["event_index"] is not None,
                "history_corrupt", "History head mismatch")
    else:
        require(state["event_head"] is None and state["event_index"] is None, "history_corrupt", "Unexpected history")
    require(state["status"] in {"active", "blocked", "completed"} and state["mode"] in {"sequential", "parallel"}, "state_schema", "Unknown execution status or mode")
    require(all(t["status"] in TASK_STATES for t in state["tasks"].values()), "state_schema", "Unknown task state")
    if view == "compact":
        from .state_view import compact
        return compact(state)
    return state


def inspect(directory, view="compact"):
    """Public views never recursively expand object references."""
    state = read(directory, view=view)
    if view == "compact":
        return state
    return state.manifest


def audit(directory):
    state = read(directory)
    seen = state.objects.audit(state)
    count = state_history.audit(state.objects, state)
    return {"revision": state["revision"], "events": count, "current_objects": len(seen), "status": "verified"}


def read_object(directory, reference):
    read(directory, view="compact")
    objects = StateObjects(directory)
    # Return one stored object, with nested references intact.
    value = json.loads(objects.raw(reference))
    require(type(value) is {"object": dict, "array": list, "string": str}[reference["kind"]],
            "object_corrupt", "Object type mismatch")
    return value


def new_task(task):
    return {"plan": task, "status": "pending", "attempt": 0, "candidate": None, "evidence": [], "reviews": [], "commits": [], "blockers": [], "review_limit": 3, "review_rounds_started": 0, "review_rounds_completed": 0, "active_review": None, "test_repair_limit": 5, "test_repair_cycles_started": 0, "active_repair": None, "repair_cycles": [], "budget_decisions": [], "checks": [], "worktree": None, "roles": [], "paths": []}


def initialize(basis, owner, parallel_request=None, isolation=False, mode="parallel"):
    require(isinstance(owner, str) and owner, "owner", "Orchestrator identity required")
    require(mode in {"parallel", "sequential"}, "mode", "Expected parallel or sequential")
    require(not parallel_request or (parallel_request.get("source") and parallel_request.get("text")), "parallel_authorization", "Record the actual execution instruction or mode request")
    mode_reason = "isolation unavailable" if mode == "parallel" and not isolation else None
    if mode_reason:
        mode = "sequential"
    parallel_request = (parallel_request or basis["instruction"]) if mode == "parallel" else None
    directory = execution_directory(basis)
    require(str(directory.parent) == basis["change_root"], "change_root", "Input root mismatch")
    with lock(directory):
        require(not storage(directory).exists(), "already_started", "Use resume for existing execution")
        run = uuid.uuid4().hex
        state = {"schema_version": 2, "change_id": basis["change_id"], "run_id": run, "revision": 0, "status": "active", "owner": owner, "basis": basis, "mode": mode, "parallel_request": parallel_request, "mode_reason": mode_reason, "tasks": {}, "roles": {}, "event_head": None, "event_index": None, "blockers": [], "updated_at": now(), "final": None}
        if basis.get("work_kind", "change") == "refactoring":
            state.update(work_kind="refactoring", **{kind: {record["id"]: record for record in basis[kind]}
                         for kind in ("acceptance", "verification")})
        for task in basis["tasks"]:
            state["tasks"][task["id"]] = new_task(task)
        state["baseline"] = snapshot(state, basis["project_root"])
        write_json(directory / "runs" / run / "input.json", StateObjects(directory).pack(basis, root=True))
        seal(state)
        save(directory, state)
    return read(directory)


def snapshot(state, root=None):
    included = [p for t in state["tasks"].values() for p in t["paths"]]
    excluded = execution_directory(state["basis"]).relative_to(resolve(state["basis"]["project_root"])).as_posix()
    return source_snapshot(root or state["basis"]["project_root"], [excluded], included)


def assert_basis(state):
    manifest = state["basis"]["manifest"]
    paths = contained_paths(state["basis"]["change_root"], (entry["path"] for entry in manifest))
    for entry, path in zip(manifest, paths):
        require(path.is_file() and digest(path.read_bytes()) == entry["sha256"], "normative_drift", entry["path"])


def apply(directory, event):
    directory = resolve(directory)
    with lock(directory):
        original = read(directory)
        require(set(event) == {"event_id", "run_id", "expected_revision", "owner", "type", "task_id", "payload"}, "event_schema", "Expected the complete typed event envelope")
        require(isinstance(event["event_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", event["event_id"]), "event_id", "Use a filesystem-safe event ID")
        fingerprint = digest(event)
        entry = state_history.lookup(original.objects, original["event_index"], event["event_id"])
        if entry is not None:
            require(entry["fingerprint"] == fingerprint, "event_conflict", "Event ID reused with another payload")
            require(entry["revision"] <= original["revision"], "history_corrupt", "Event is not committed")
            return entry["result"]
        require(event["run_id"] == original["run_id"], "run_mismatch", "Wrong execution run")
        require(event["owner"] == original["owner"], "owner_mismatch", "Another orchestrator owns this run")
        require(type(event["expected_revision"]) is int and event["expected_revision"] == original["revision"], "revision_conflict", "Re-read current state")
        require(event["task_id"] is None or event["task_id"] in original["tasks"], "unknown_task", "Unknown TASK-ID")
        state = deepcopy(original)
        if event["type"] in {"resume", "finalize"}:
            audit(directory)
        from .transitions import reduce
        result = reduce(state, event, directory)
        state["revision"] += 1
        state["updated_at"] = now()
        if event["type"] == "check_run" and event["task_id"] and event["payload"].get("stage") == "baseline":
            state["tasks"][event["task_id"]]["baseline_event"] = {"event_id": event["event_id"], "log": result.get("log")}
        state_history.append(original.objects, state, event, result)
        seal(state)
        save(directory, state)
    return result
