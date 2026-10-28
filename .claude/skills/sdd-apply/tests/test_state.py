import json
import pytest
from lib.state import initialize, read, apply, lock
from lib.state_storage import storage


@pytest.fixture
def store(basis):
    state = initialize(basis, isolation=True)
    return basis["change_root"] + "/execution", state


def event(state, kind="block", **changes):
    return {"event_id": "e1", "run_id": state["run_id"], "expected_revision": state["revision"], "type": kind, "task_id": "TASK-one", "payload": {"reason": "test", "resume_condition": "fixed"}, **changes}


def test_atomic_idempotency(store):
    directory, state = store
    assert "checks" not in state["basis"]
    assert "dirty_paths" not in state["basis"]
    item = event(state)
    result = apply(directory, item)
    assert apply(directory, item) == result
    assert read(directory)["revision"] == 1
    with pytest.raises(ValueError, match="reused"):
        apply(directory, {**item, "payload": {"reason": "different"}})
    assert read(directory)["revision"] == 1


@pytest.mark.parametrize("changes", [{"type": "DONE"}, {"expected_revision": 4}, {"task_id": "TASK-missing"}, {"type": "start", "payload": {}}])
def test_rejection_keeps_bytes(store, changes):
    from pathlib import Path
    directory, state = store
    before = storage(directory).read()
    with pytest.raises(ValueError):
        apply(directory, event(state, **changes))
    assert storage(directory).read() == before


# Exercise the real lock file; the memory adapter cannot prove filesystem exclusion.
@pytest.mark.native_state
def test_lock_and_corrupt_history(store):
    from pathlib import Path
    directory, state = store
    with lock(directory):
        with pytest.raises(ValueError, match="locked"):
            apply(directory, event(state))
    path = Path(directory) / "state.json"
    data = json.loads(path.read_text())
    data["revision"] = 8
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="integrity"):
        read(directory)


# Separate interpreters must contend for one revision through the real filesystem lock.
@pytest.mark.native_state
def test_two_processes_one_revision(store, tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    directory, state = store
    script_root = str(Path(__file__).resolve().parents[1] / "scripts")
    code = "import sys,json; sys.dont_write_bytecode=True; sys.path.insert(0,sys.argv[1]); from lib.state import apply; apply(sys.argv[2],json.loads(sys.argv[3]))"
    a = subprocess.Popen([sys.executable, "-B", "-c", code, script_root, directory, json.dumps(event(state, event_id="a"))], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    b = subprocess.Popen([sys.executable, "-B", "-c", code, script_root, directory, json.dumps(event(state, event_id="b"))], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    a.communicate(timeout=20)
    b.communicate(timeout=20)
    assert sorted([a.returncode, b.returncode]) == [0, 1]
    assert read(directory)["revision"] == 1


# Inject failure at the OS replacement boundary and verify persisted bytes survive.
@pytest.mark.native_state
def test_interrupted_replace_preserves_state(store, monkeypatch):
    from lib import common
    from pathlib import Path
    directory, state = store
    before = storage(directory).read()
    def fail(*args):
        raise OSError("interrupted before atomic replace")
    monkeypatch.setattr(common.os, "replace", fail)
    with pytest.raises(OSError, match="interrupted"):
        apply(directory, event(state))
    assert storage(directory).read() == before
