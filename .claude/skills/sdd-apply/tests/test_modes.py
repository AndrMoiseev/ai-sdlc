"""Parallel execution is the only supported mode; legacy states stay untouched."""
from pathlib import Path
import pytest
from lib.state import initialize, read, save, seal
from lib.api import dispatch
from lib.common import Rejected
from lib.state_storage import storage
from conftest import Driver


@pytest.mark.parametrize("isolation", [False, True])
def test_initialize_requires_isolation(project, isolation):
    instruction = {"source": "user", "text": "Execute the approved plan"}
    args = {"project_root": str(project), "change": "demo", "instruction": instruction,
            "isolation": isolation}
    if not isolation:
        with pytest.raises(Rejected) as failure:
            dispatch({"operation": "initialize", "args": args})
        assert failure.value.code == "isolation_required"
        return
    state = dispatch({"operation": "initialize", "args": args})
    assert "mode" not in state
    assert state["basis"]["instruction"] == instruction
    assert "parallel_request" not in state
    assert "owner" not in state
    assert "document_records" not in state["basis"]


def test_parallel_admits_worktree_and_survives_resume(basis, tmp_path):
    driver = Driver(basis)
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    assert driver.task["worktree"]
    driver.send("resume", {"host_trace": "synthetic-host", "live_contexts": []}, task_id=None)
    assert "mode" not in driver.state
    assert driver.state["basis"]["instruction"] == basis["instruction"]


@pytest.mark.parametrize("mode", ["parallel", "sequential", "automatic"])
def test_unsupported_mode_leaves_no_state(basis, mode):
    with pytest.raises(TypeError, match="mode"):
        initialize(basis, isolation=True, mode=mode)
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


@pytest.mark.parametrize("kind", ["mode", "handoff"])
def test_removed_event_is_not_supported(driver, kind):
    before = storage(driver.directory).read()
    with pytest.raises(ValueError, match="unknown_event"):
        driver.send(kind, {}, task_id=None)
    assert storage(driver.directory).read() == before
