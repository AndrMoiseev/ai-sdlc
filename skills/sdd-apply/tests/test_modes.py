import pytest
from lib.state import initialize
from lib.api import dispatch
from conftest import Driver, SPEC


def test_mode_change_requires_fresh_owner(driver):
    driver.send("mode", {"mode": "parallel", "text": "Run independent tasks in parallel", "source": "user", "isolation_available": True}, task_id=None)
    assert driver.state["status"] == "blocked"
    assert driver.state["mode"] == "sequential"
    with pytest.raises(ValueError):
        driver.send("handoff", {"new_owner": "owner", "fresh": True, "launch_ref": "test"}, task_id=None)
    driver.send("handoff", {"new_owner": "new-owner", "fresh": True, "launch_ref": "synthetic-host"}, task_id=None)
    assert driver.state["mode"] == "parallel"
    assert driver.state["owner"] == "new-owner"


def test_parallel_without_isolation_defaults_sequential(basis):
    state = initialize(basis, "owner", {"source": "user", "text": "parallel"}, isolation=False)
    assert state["mode"] == "sequential"
    assert state["parallel_request"] is None
    assert state["mode_reason"] == "isolation unavailable"


@pytest.mark.parametrize("isolation", [False, True])
@pytest.mark.parametrize("mode", [None, "sequential", "parallel"])
def test_initialize_mode_selection(project, isolation, mode):
    instruction = {"source": "user", "text": "Execute the approved plan"}
    args = {"project_root": str(project), "change": "demo", "instruction": instruction,
            "sdd_spec": str(SPEC), "owner": "owner", "isolation": isolation}
    if mode is not None:
        args["mode"] = mode
    state = dispatch({"operation": "initialize", "args": args})
    parallel = isolation and mode != "sequential"
    assert state["mode"] == ("parallel" if parallel else "sequential")
    assert state["parallel_request"] == (instruction if parallel else None)
    assert state["mode_reason"] == ("isolation unavailable" if not isolation and mode != "sequential" else None)


def test_default_parallel_admits_worktree_and_survives_resume(basis, tmp_path):
    driver = Driver(basis, parallel=True)
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    assert driver.task["worktree"]
    driver.send("resume", {"host_trace": "synthetic-host", "live_contexts": []}, task_id=None)
    assert driver.state["mode"] == "parallel"
    assert driver.state["parallel_request"] == basis["instruction"]


def test_explicit_sequential_survives_resume(driver):
    driver.send("resume", {"host_trace": "synthetic-host", "live_contexts": []}, task_id=None)
    assert driver.state["mode"] == "sequential"
    with pytest.raises(ValueError, match="parallel mode required"):
        driver.send("worktree_create", {"workspace": "unused"})


def test_legacy_parallel_request_is_preserved(basis):
    request = {"source": "user", "text": "Run tasks in parallel"}
    state = initialize(basis, "owner", request, isolation=True)
    assert state["mode"] == "parallel"
    assert state["parallel_request"] == request


def test_invalid_mode_leaves_no_state(basis):
    from pathlib import Path
    with pytest.raises(ValueError, match="Expected parallel or sequential"):
        initialize(basis, "owner", isolation=True, mode="automatic")
    assert not (Path(basis["change_root"]) / "execution/state.json").exists()


def test_revision_cannot_bypass_pending_sequential_handoff(basis):
    driver = Driver(basis, parallel=True)
    driver.send("mode", {"mode": "sequential", "text": "Switch to sequential", "source": "user"}, task_id=None)
    before = driver.state
    with pytest.raises(ValueError, match="pending mode handoff"):
        driver.send("revised_plan", {"instruction": {"text": "Execute revised plan", "source": "user"}}, task_id=None)
    assert driver.state == before
    assert driver.state["status"] == "blocked"
