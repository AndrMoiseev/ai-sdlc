import pytest
from lib.state import initialize


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
