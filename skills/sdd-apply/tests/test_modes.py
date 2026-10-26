"""Parallel execution is the only supported mode; legacy states stay untouched."""
from pathlib import Path
import pytest
from lib.state import initialize, read, save, seal
from lib.api import dispatch
from lib.common import Rejected
from lib.state_storage import storage
from conftest import Driver, SPEC


def test_handoff_requires_fresh_owner_and_preserves_execution(driver):
    before = driver.state
    with pytest.raises(ValueError):
        driver.send("handoff", {"new_owner": "owner", "fresh": True, "launch_ref": "test"}, task_id=None)
    driver.send("handoff", {"new_owner": "new-owner", "fresh": True, "launch_ref": "synthetic-host"}, task_id=None)
    assert driver.state["owner"] == "new-owner"
    assert driver.state["mode"] == "parallel"
    assert driver.state["tasks"] == before["tasks"]


@pytest.mark.parametrize("isolation", [False, True])
def test_initialize_requires_isolation(project, isolation):
    instruction = {"source": "user", "text": "Execute the approved plan"}
    args = {"project_root": str(project), "change": "demo", "instruction": instruction,
            "sdd_spec": str(SPEC), "owner": "owner", "isolation": isolation}
    if not isolation:
        with pytest.raises(Rejected) as failure:
            dispatch({"operation": "initialize", "args": args})
        assert failure.value.code == "isolation_required"
        return
    state = dispatch({"operation": "initialize", "args": args})
    assert state["mode"] == "parallel"
    assert state["parallel_request"] == instruction


def test_parallel_admits_worktree_and_survives_resume(basis, tmp_path):
    driver = Driver(basis)
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    assert driver.task["worktree"]
    driver.send("resume", {"host_trace": "synthetic-host", "live_contexts": []}, task_id=None)
    assert driver.state["mode"] == "parallel"
    assert driver.state["parallel_request"] == basis["instruction"]


def test_explicit_parallel_request_is_preserved(basis):
    request = {"source": "user", "text": "Run tasks in parallel"}
    state = initialize(basis, "owner", request, isolation=True, mode="parallel")
    assert state["mode"] == "parallel" and state["parallel_request"] == request


@pytest.mark.parametrize("mode", ["sequential", "automatic"])
def test_unsupported_mode_leaves_no_state(basis, mode):
    with pytest.raises(ValueError, match="Only parallel execution"):
        initialize(basis, "owner", isolation=True, mode=mode)
    assert not storage(Path(basis["change_root"]) / "execution").exists()


@pytest.mark.parametrize("legacy", [{"mode": "sequential"}, {"pending_mode": {"mode": "sequential"}}])
def test_legacy_execution_is_rejected_without_rewriting(driver, legacy):
    state = driver.state
    state.update(legacy)
    save(driver.directory, seal(state))
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as failure:
        read(driver.directory)
    assert failure.value.code == "unsupported_execution_mode"
    assert storage(driver.directory).read() == before


def test_mode_event_is_not_supported(driver):
    before = storage(driver.directory).read()
    with pytest.raises(ValueError, match="unknown_event"):
        driver.send("mode", {"mode": "sequential"}, task_id=None)
    assert storage(driver.directory).read() == before
