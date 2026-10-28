"""State v2 size, selective reads, immutable evidence and crash boundaries."""
from copy import deepcopy
import json

import pytest

from lib import artifact_storage as artifacts, state_history
from lib.common import digest
from lib.state import apply, audit, inspect, read, save, seal
from lib.state_objects import StateObjects
from lib.state_storage import storage


def test_legacy_execution_requires_explicit_migration(driver):
    state = driver.state
    state["schema_version"] = 2
    save(driver.directory, seal(state))
    before = storage(driver.directory).read()
    with pytest.raises(ValueError, match="explicitly reconcile"):
        read(driver.directory)
    assert storage(driver.directory).read() == before



def event(state, ident):
    return {"event_id": ident, "run_id": state["run_id"], "expected_revision": state["revision"],
            "type": "block", "task_id": "TASK-one",
            "payload": {"reason": ident, "resume_condition": "fixed"}}


# Native coverage checks that the manifest and external objects round-trip together on disk.
@pytest.mark.parametrize("implementation", ["memory", pytest.param("file", marks=pytest.mark.native_state)])
def test_repeated_large_snapshots_are_stored_once_and_loaded_on_demand(driver, implementation, monkeypatch):
    state = driver.state
    files = {f"source-{n}.py": {"sha256": digest(str(n))} for n in range(1000)}
    snapshot = {"files": files, "digest": digest(files)}
    task = state["tasks"]["TASK-one"]
    task["start_snapshot"] = deepcopy(snapshot)
    task["freeze_base"] = deepcopy(snapshot)
    task["prior_result"] = {"evidence": [{"source": deepcopy(snapshot)} for _ in range(20)]}
    save(driver.directory, seal(state))
    packed = json.loads(storage(driver.directory).read())
    assert len(storage(driver.directory).read()) < 16384
    objects = StateObjects(driver.directory)
    loaded = read(driver.directory)
    packed_task = objects.pack(loaded["tasks"]["TASK-one"], root=True)
    assert packed_task["start_snapshot"] == packed_task["freeze_base"]
    original = artifacts.read_bytes
    touched = []
    def observe(path):
        touched.append(str(path))
        return original(path)
    monkeypatch.setattr(artifacts, "read_bytes", observe)
    inspect(driver.directory)
    assert not any(packed_task["start_snapshot"]["$object"]["sha256"] in p for p in touched)
    assert not any(packed_task["prior_result"]["$object"]["sha256"] in p for p in touched)
    assert loaded["tasks"]["TASK-one"]["start_snapshot"] == snapshot
    assert audit(driver.directory)["status"] == "verified"


def test_old_history_corruption_requires_audit_and_blocks_resume(driver):
    first = event(driver.state, "first")
    apply(driver.directory, first)
    reference = read(driver.directory)["event_head"]
    apply(driver.directory, event(driver.state, "second"))
    path = StateObjects(driver.directory).path(reference)
    artifacts.write(path, b"corrupt historical event")
    assert inspect(driver.directory)["revision"] == 2
    with pytest.raises(ValueError) as failure:
        audit(driver.directory)
    assert failure.value.code == "object_corrupt"
    resume = event(driver.state, "resume") | {"type": "resume", "task_id": None,
        "payload": {"host_trace": "test", "live_contexts": []}}
    before = storage(driver.directory).read()
    with pytest.raises(ValueError) as failure:
        apply(driver.directory, resume)
    assert failure.value.code == "object_corrupt"
    assert storage(driver.directory).read() == before


def test_uncommitted_event_is_not_replayed_after_failed_manifest_replace(driver, monkeypatch):
    import lib.state as state_module
    first = event(driver.state, "uncommitted")
    original = state_module.save
    def fail(*args):
        raise OSError("manifest replace failed")
    monkeypatch.setattr(state_module, "save", fail)
    with pytest.raises(OSError, match="manifest"):
        apply(driver.directory, first)
    monkeypatch.setattr(state_module, "save", original)
    assert read(driver.directory)["revision"] == 0
    second = event(driver.state, "committed")
    result = apply(driver.directory, second)
    assert apply(driver.directory, second) == result
    with pytest.raises(ValueError, match="Re-read current state"):
        apply(driver.directory, first)
    assert audit(driver.directory)["events"] == 1


@pytest.fixture
def event_history(basis):
    """Build authentic history once in memory, then publish to the tested store.

    This test measures lookup over existing history. Native transaction writes
    and crash boundaries have their own contracts in this module/test_state.py.
    """
    from conftest import Driver
    from memory_state import MemoryStates
    from lib.artifact_storage import use_artifacts
    from lib.state_storage import use_storage
    memory = MemoryStates()
    requests = []
    with use_storage(memory), use_artifacts(memory.artifacts):
        driver = Driver(basis)
        for number in range(25):
            item = event(driver.state, f"event-{number}")
            requests.append(item)
            apply(driver.directory, item)
    target = storage(driver.directory)
    for path, content in memory.artifacts.files.items():
        artifacts.write(path, content)
    target.replace(memory(driver.directory).read())
    return driver, requests


def test_idempotency_index_does_not_scan_the_event_chain(event_history, monkeypatch):
    driver, requests = event_history
    count = 0
    original = artifacts.read_bytes
    def observe(path):
        nonlocal count
        count += 1
        return original(path)
    monkeypatch.setattr(artifacts, "read_bytes", observe)
    apply(driver.directory, requests[0])
    assert count < 15
    assert audit(driver.directory)["events"] == 25


def test_sealed_manifest_is_detached_from_later_mutations(driver):
    state = driver.state
    packed = seal(state)
    state["tasks"]["TASK-one"]["blockers"].append({"reason": "later mutation"})
    # An unopened reference is mutable too; sealing must detach its descriptor.
    dict.__getitem__(state, "baseline")["$object"]["bytes"] += 1
    save(driver.directory, packed)
    assert read(driver.directory)["tasks"]["TASK-one"]["blockers"] == []
    assert read(driver.directory)["baseline"]["commit"]


def test_audit_rereads_objects_and_rejects_tampering(driver):
    apply(driver.directory, event(driver.state, "first"))
    assert audit(driver.directory)["events"] == 1
    reference = read(driver.directory)["event_head"]
    artifacts.write(StateObjects(driver.directory).path(reference), b"corrupt")
    with pytest.raises(ValueError) as failure:
        audit(driver.directory)
    assert failure.value.code == "object_corrupt"


@pytest.mark.parametrize("damage", ["missing", "bytes", pytest.param("path", marks=pytest.mark.native_paths)])
def test_accessed_object_is_verified(driver, damage):
    state = driver.state
    state["baseline"] = {"files": {"source": "x" * 5000}, "digest": "test"}
    seal(state)
    save(driver.directory, state)
    packed = json.loads(storage(driver.directory).read())
    reference = packed["baseline"]["$object"]
    if damage == "path":
        reference["path"] = "../outside.json"
        packed["integrity"] = digest({k: v for k, v in packed.items() if k != "integrity"})
        storage(driver.directory).save(packed)
    else:
        path = StateObjects(driver.directory).path(reference)
        if damage == "missing":
            artifacts.remove(path)
        else:
            artifacts.write(path, b"{}")
    current = read(driver.directory)
    with pytest.raises(ValueError) as failure:
        current["baseline"]
    assert failure.value.code == {"missing": "object_missing", "bytes": "object_corrupt", "path": "object_reference"}[damage]


def test_lazy_copy_and_nested_mutations_are_independent(driver):
    original = read(driver.directory)
    manifest = original.manifest
    copied = deepcopy(original)
    copied["tasks"]["TASK-one"]["evidence"].append({"outcome": "failed"})
    copied["tasks"]["TASK-one"].setdefault("checks", []).append({"id": "new"})
    assert original["tasks"]["TASK-one"]["evidence"] == []
    assert original["tasks"]["TASK-one"]["checks"] == []
    assert original.manifest == manifest
    seal(copied)
    save(driver.directory, copied)
    assert read(driver.directory)["tasks"]["TASK-one"]["evidence"] == [{"outcome": "failed"}]


def test_object_size_boundary_counts_json_escapes(driver):
    objects = StateObjects(driver.directory)
    for value in ("x" * 4094, "x" * 4095, "\n" * 2047, "\n" * 2048,
                  "\U0001f642" * 341, "\U0001f642" * 342, [0] * 2048,
                  {"quoted\"key": [0] * 1024, "other": [1] * 1024}):
        packed = objects.pack(value)
        external = len(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()) > 4096
        assert (isinstance(packed, dict) and set(packed) == {"$object"}) == external
        assert objects.open(packed) == value
