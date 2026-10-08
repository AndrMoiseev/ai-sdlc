"""Revisioned event store. Rejected transitions never replace the state file."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import uuid
import re
from .common import atomic, contained, digest, now, require, source_snapshot, write_json

TASK_STATES = {"pending", "running", "verifying", "reviewing", "integrating", "repairing", "committing", "blocked", "accepted"}


@contextmanager
def lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError(f"state_locked: inspect owner before recovery: {path}")
    token = uuid.uuid4().hex
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"pid": os.getpid(), "host": socket.gethostname(), "token": token}, stream)
        yield
    finally:
        if path.exists() and json.loads(path.read_text())["token"] == token:
            path.unlink()


def recover_lock(directory):
    path = Path(directory) / "state.lock"
    owner = json.loads(path.read_text())
    require(owner["host"] == socket.gethostname(), "unknown_lock_owner", "Owner is on another host")
    # A failed permission check does not prove death. Windows kill(pid, 0) is
    # unsafe; OpenProcess/GetExitCodeProcess is the read-only liveness probe.
    if os.name == "nt":
        import ctypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.restype = ctypes.c_void_p
        handle = api.OpenProcess(0x1000, False, owner["pid"])
        if handle:
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            api.CloseHandle(handle)
            raise ValueError("lock_owner_alive")
        require(ctypes.get_last_error() == 87, "unknown_lock_owner", "Cannot prove owner exited")
    else:
        try:
            os.kill(owner["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError("lock_owner_alive")
    require(json.loads(path.read_text()) == owner, "lock_changed", "Lock changed during recovery")
    path.unlink()
    return {"recovered": owner}


def seal(state):
    state["integrity"] = digest({k: v for k, v in state.items() if k != "integrity"})


def read(directory):
    state = json.loads((Path(directory) / "state.json").read_text(encoding="utf-8"))
    require(state.get("schema_version") == 1, "state_version", "Unsupported state schema")
    expected_directory = contained(state["basis"]["project_root"], "sdd/changes/" + state["change_id"] + "/execution")
    require(Path(directory).resolve() == expected_directory and expected_directory.parent == Path(state["basis"]["change_root"]).resolve(), "state_root", "State is outside its registered execution root")
    require(state.get("integrity") == digest({k: v for k, v in state.items() if k != "integrity"}), "state_corrupt", "State integrity mismatch")
    require(state["revision"] == len(state["events"]), "history_corrupt", "History length mismatch")
    require(state["status"] in {"active", "blocked", "completed"} and state["mode"] in {"sequential", "parallel"}, "state_schema", "Unknown execution status or mode")
    require(all(t["status"] in TASK_STATES for t in state["tasks"].values()), "state_schema", "Unknown task state")
    previous = None
    ids = set()
    for number, entry in enumerate(state["events"], 1):
        require(entry["revision"] == number and entry["previous"] == previous and entry["event_id"] not in ids, "history_corrupt", "Event chain mismatch")
        require(entry["hash"] == digest({k: v for k, v in entry.items() if k != "hash"}), "history_corrupt", "Event hash mismatch")
        ids.add(entry["event_id"])
        previous = entry["hash"]
    return state


def new_task(task):
    return {"plan": task, "status": "pending", "attempt": 0, "candidate": None, "evidence": [], "reviews": [], "commits": [], "blockers": [], "review_limit": 3, "review_rounds_started": 0, "review_rounds_completed": 0, "active_review": None, "test_repair_limit": 5, "test_repair_cycles_started": 0, "active_repair": None, "repair_cycles": [], "budget_decisions": [], "checks": [], "worktree": None, "roles": [], "paths": []}


def initialize(basis, owner, parallel_request=None, isolation=False):
    require(isinstance(owner, str) and owner, "owner", "Orchestrator identity required")
    directory = contained(basis["project_root"], "sdd/changes/" + basis["change_id"] + "/execution")
    require(str(directory.parent) == basis["change_root"], "change_root", "Input root mismatch")
    with lock(directory):
        require(not (directory / "state.json").exists(), "already_started", "Use resume for existing execution")
        run = uuid.uuid4().hex
        state = {"schema_version": 1, "change_id": basis["change_id"], "run_id": run, "revision": 0, "status": "active", "owner": owner, "basis": basis, "mode": "parallel" if parallel_request and isolation else "sequential", "parallel_request": parallel_request if isolation else None, "mode_reason": "isolation unavailable" if parallel_request and not isolation else None, "tasks": {}, "roles": {}, "events": [], "blockers": [], "updated_at": now(), "final": None}
        require(not parallel_request or (parallel_request.get("source") and parallel_request.get("text")), "parallel_authorization", "Explicit scoped user request required")
        for task in basis["tasks"]:
            state["tasks"][task["id"]] = new_task(task)
        state["baseline"] = snapshot(state, basis["project_root"])
        write_json(directory / "runs" / run / "input.json", basis)
        seal(state)
        write_json(directory / "state.json", state)
    return state


def snapshot(state, root=None):
    included = [p for t in state["tasks"].values() for p in t["paths"]]
    return source_snapshot(root or state["basis"]["project_root"], [f"sdd/changes/{state['change_id']}/execution"], included)


def assert_basis(state):
    for entry in state["basis"]["manifest"]:
        path = contained(state["basis"]["change_root"], entry["path"])
        require(path.is_file() and digest(path.read_bytes()) == entry["sha256"], "normative_drift", entry["path"])


def apply(directory, event):
    directory = Path(directory).resolve()
    with lock(directory):
        original = read(directory)
        require(set(event) == {"event_id", "run_id", "expected_revision", "owner", "type", "task_id", "payload"}, "event_schema", "Expected the complete typed event envelope")
        require(isinstance(event["event_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", event["event_id"]), "event_id", "Use a filesystem-safe event ID")
        fingerprint = digest(event)
        for entry in original["events"]:
            if entry["event_id"] == event["event_id"]:
                require(entry["fingerprint"] == fingerprint, "event_conflict", "Event ID reused with another payload")
                return entry["result"]
        require(event["run_id"] == original["run_id"], "run_mismatch", "Wrong execution run")
        require(event["owner"] == original["owner"], "owner_mismatch", "Another orchestrator owns this run")
        require(type(event["expected_revision"]) is int and event["expected_revision"] == original["revision"], "revision_conflict", "Re-read current state")
        require(event["task_id"] is None or event["task_id"] in original["tasks"], "unknown_task", "Unknown TASK-ID")
        state = deepcopy(original)
        from .transitions import reduce
        result = reduce(state, event, directory)
        state["revision"] += 1
        state["updated_at"] = now()
        entry = {"event_id": event["event_id"], "fingerprint": fingerprint, "event": event, "revision": state["revision"], "previous": state["events"][-1]["hash"] if state["events"] else None, "result": result, "time": state["updated_at"]}
        entry["hash"] = digest(entry)
        state["events"].append(entry)
        seal(state)
        write_json(directory / "state.json", state)
    return result
