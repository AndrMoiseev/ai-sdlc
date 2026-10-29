"""Revisioned event store. Rejected transitions never replace the state file."""
from dataclasses import dataclass
import json
from pathlib import Path
import uuid
import re
from .common import contained, digest, now, require, write_json

from .state_storage import storage
from .path_resolution import resolve
from .state_objects import StateObjects
from . import state_history

TASK_STATES = {"pending", "running", "verifying", "reviewing", "integrating", "repairing", "committing", "blocked", "accepted"}


def lock(directory):
    return storage(directory).lock()


def recover_lock(directory):
    return storage(directory).recover_lock()


@dataclass(frozen=True)
class SealedState:
    """The detached manifest whose integrity was calculated by seal()."""
    manifest: dict


def save(directory, state):
    packed = state.manifest if isinstance(state, SealedState) else StateObjects(directory).pack(state, root=True)
    storage(directory).save(packed)


def seal(state):
    objects = StateObjects(execution_directory(state["basis"]))
    packed = objects.pack(state, root=True)
    state["integrity"] = digest({k: v for k, v in packed.items() if k != "integrity"})
    packed["integrity"] = state["integrity"]
    return SealedState(packed)


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
    raw = storage(directory).read()
    packed = json.loads(raw)
    require(packed.get("schema_version") == 3, "state_version", "Expected execution state schema 3; preserve legacy execution and explicitly reconcile its approved plan before migration")
    require(packed.get("integrity") == digest({k: v for k, v in packed.items() if k != "integrity"}), "state_corrupt", "State integrity mismatch")
    state = StateObjects(directory).open(packed)
    state.manifest_bytes = raw
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
    require(state["status"] in {"active", "blocked", "completed"}, "state_schema", "Unknown execution status")
    require(state.get("mode", "parallel") == "parallel" and not state.get("pending_mode"), "unsupported_execution_mode",
            "Only parallel execution is supported; preserve this state and use its original skill version to reconcile it")
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
    with state.objects.cached_reads():
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
    return {"plan": task, "status": "pending", "attempt": 0, "evidence": [], "verification_results": [], "reviews": [], "commits": [], "blockers": [], "review_limit": 3, "review_rounds_started": 0, "review_rounds_completed": 0, "active_review": None, "test_repair_limit": 5, "test_repair_cycles_started": 0, "active_repair": None, "repair_cycles": [], "budget_decisions": [], "checks": [], "worktree": None, "roles": [], "paths": []}


def initialize(basis, isolation=False):
    require(isolation, "isolation_required", "Execution requires isolated task worktrees")
    directory = execution_directory(basis)
    require(str(directory.parent) == basis["change_root"], "change_root", "Input root mismatch")
    with lock(directory):
        require(not storage(directory).exists(), "already_started", "Use resume for existing execution")
        run = uuid.uuid4().hex
        state = {"schema_version": 3, "change_id": basis["change_id"], "run_id": run, "revision": 0, "status": "active", "basis": basis, "tasks": {}, "roles": {}, "event_head": None, "event_index": None, "blockers": [], "updated_at": now(), "final": None}
        if basis.get("work_kind", "change") == "refactoring":
            state.update(work_kind="refactoring", **{kind: {record["id"]: record for record in basis[kind]}
                         for kind in ("acceptance", "verification")})
        for task in basis["tasks"]:
            state["tasks"][task["id"]] = new_task(task)
        state["baseline"] = snapshot(state, basis["project_root"])
        state["execution_head"] = basis["head"]
        write_json(directory / "runs" / run / "input.json", StateObjects(directory).pack(basis, root=True))
        save(directory, seal(state))
    return read(directory)


def snapshot(state, root=None):
    """Hash change documents only; Git identifies the code being checked."""
    from .repository import repository
    import os
    project = resolve(state["basis"]["project_root"])
    relative = resolve(state["basis"]["change_root"]).relative_to(project)
    root = resolve(root or project)
    change = contained(root, relative.as_posix())
    files = {}
    pending = [change]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if directory == change and entry.name == "execution":
                    continue
                path = Path(entry.path)
                require(not entry.is_symlink() and not (hasattr(entry, "is_junction") and entry.is_junction()),
                        "unsupported_file", str(path))
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    files[(relative / path.relative_to(change)).as_posix()] = {"sha256": digest(path.read_bytes())}
    excluded = (relative / "execution").as_posix()
    status = repository(root).status(exclude=[excluded])
    return dict(files=files, digest=digest(files), commit=status["head"],
                branch=status["branch"], dirty_paths=status["dirty_paths"])


def clean_source(source):
    require(source.get("commit"), "legacy_candidate", "Source snapshots require explicit rebaseline in a task worktree; preserve historical evidence")
    require(not source["dirty_paths"], "dirty_candidate", "Commit or preserve changes before verification: " + ", ".join(source["dirty_paths"]))


def execution_source(state):
    from .repository import repository
    basis = state["basis"]
    excluded = execution_directory(basis).relative_to(Path(basis["project_root"])).as_posix()
    return repository(basis["project_root"]).status(exclude=[excluded])


def assert_basis(state):
    basis = state["basis"]
    require(basis.get("schema_version") == 2 and "manifest" not in basis,
            "basis_migration", "Reconcile legacy document manifests into the current execution basis")
    require(isinstance(basis.get("head"), str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", basis["head"]),
            "basis_commit", "Execution basis needs its admission commit OID")
    # Ongoing execution advances HEAD. Admission checks and explicit plan
    # replacement govern authorization; current Git state gates govern integrity.

def apply(directory, event):
    directory = resolve(directory)
    with lock(directory):
        original = read(directory)
        require(set(event) == {"event_id", "run_id", "expected_revision", "type", "task_id", "payload"}, "event_schema", "Expected the complete typed event envelope")
        require(isinstance(event["event_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", event["event_id"]), "event_id", "Use a filesystem-safe event ID")
        fingerprint = digest(event)
        entry = state_history.lookup(original.objects, original["event_index"], event["event_id"])
        if entry is not None:
            require(entry["fingerprint"] == fingerprint, "event_conflict", "Event ID reused with another payload")
            require(entry["revision"] <= original["revision"], "history_corrupt", "Event is not committed")
            return entry["result"]
        require(event["run_id"] == original["run_id"], "run_mismatch", "Wrong execution run")
        require(type(event["expected_revision"]) is int and event["expected_revision"] == original["revision"], "revision_conflict", "Re-read current state")
        require(event["task_id"] is None or event["task_id"] in original["tasks"], "unknown_task", "Unknown TASK-ID")
        # read() decoded private bytes for this operation. Reducer mutations
        # cannot affect persisted state until the atomic save succeeds.
        state = original
        if event["type"] in {"resume", "finalize"}:
            audit(directory)
        from .transitions import reduce
        result = reduce(state, event, directory)
        task = state["tasks"].get(event["task_id"])
        main_candidate = event["type"] == "candidate" and task and task.get("worktree", {}).get("integrated")
        if main_candidate or event["type"] in {"commit", "revised_plan"}:
            from .repository import repository
            state["execution_head"] = repository(state["basis"]["project_root"]).head()
        state["revision"] += 1
        state["updated_at"] = now()
        if event["type"] == "check_run" and event["task_id"] and event["payload"].get("stage") == "baseline":
            state["tasks"][event["task_id"]]["baseline_event"] = {"event_id": event["event_id"], "log": result.get("log")}
        state_history.append(original.objects, state, event, result)
        save(directory, seal(state))
    return result
