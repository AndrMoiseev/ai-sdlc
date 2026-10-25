"""State v2 size, selective reads, immutable evidence and crash boundaries."""
from copy import deepcopy
import json

import pytest

from lib import artifact_storage as artifacts, state_history
from lib.common import digest
from lib.state import apply, audit, inspect, read, save, seal
from lib.state_objects import StateObjects
from lib.state_storage import storage


pytestmark = pytest.mark.parametrize("implementation", [
    "memory", pytest.param("file", marks=pytest.mark.native_state),
])


def event(state, ident):
    return {"event_id": ident, "run_id": state["run_id"], "expected_revision": state["revision"],
            "owner": state["owner"], "type": "block", "task_id": "TASK-one",
            "payload": {"reason": ident, "resume_condition": "fixed"}}


def test_repeated_large_snapshots_are_stored_once_and_loaded_on_demand(driver, implementation, monkeypatch):
    state = driver.state
    files = {f"source-{n}.py": {"sha256": digest(str(n))} for n in range(1000)}
    snapshot = {"files": files, "digest": digest(files)}
    task = state["tasks"]["TASK-one"]
    task["start_snapshot"] = deepcopy(snapshot)
    task["freeze_base"] = deepcopy(snapshot)
    task["prior_result"] = {"evidence": [{"source": deepcopy(snapshot)} for _ in range(20)]}
    seal(state)
    save(driver.directory, state)
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


def test_old_history_corruption_requires_audit_and_blocks_resume(driver, implementation):
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


def test_uncommitted_event_is_not_replayed_after_failed_manifest_replace(driver, implementation, monkeypatch):
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


def test_idempotency_index_does_not_scan_the_event_chain(driver, implementation, monkeypatch):
    requests = []
    for number in range(25):
        item = event(driver.state, f"event-{number}")
        requests.append(item)
        apply(driver.directory, item)
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


@pytest.mark.parametrize("damage", ["missing", "bytes", "path"])
def test_accessed_object_is_verified(driver, implementation, damage):
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


def test_lazy_copy_and_nested_mutations_are_independent(driver, implementation):
    original = read(driver.directory)
    copied = deepcopy(original)
    copied["tasks"]["TASK-one"]["evidence"].append({"outcome": "failed"})
    copied["tasks"]["TASK-one"].setdefault("checks", []).append({"id": "new"})
    assert original["tasks"]["TASK-one"]["evidence"] == []
    assert original["tasks"]["TASK-one"]["checks"] == []
    seal(copied)
    save(driver.directory, copied)
    assert read(driver.directory)["tasks"]["TASK-one"]["evidence"] == [{"outcome": "failed"}]
