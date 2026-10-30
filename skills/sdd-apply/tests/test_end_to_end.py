import pytest
from lib.api import dispatch
from test_commits import prepared


def test_full_lifecycle(driver, project):
    prepared(driver, project)
    driver.send("commit")
    driver.send("accept")
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "complete"
    assert result["accepted_criteria"] == ["AC-one"]
    assert driver.state["status"] == "completed"
    view = dispatch({"operation": "dashboard", "args": {"directory": str(driver.directory)}})
    assert view["revision"] == driver.state["revision"]


def test_completion_uses_accepted_task_evidence(execution_checkpoint, monkeypatch):
    from lib import verification
    driver = execution_checkpoint("accepted")
    before = driver.state
    def unexpected(*args, **kwargs):
        pytest.fail("Completion must not run checks again")
    monkeypatch.setattr(verification.check_runner, "run_command", unexpected)
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "complete"
    assert result["accepted_criteria"] == ["AC-one"]
    assert driver.state["status"] == "completed"
    assert driver.state["roles"] == before["roles"]
    assert driver.task["evidence"] == before["tasks"]["TASK-one"]["evidence"]
    assert result["verification_results"][0]["basis"] == driver.task["verification_results"][-1]["basis"]
    assert result["verification_results"][0]["basis"]["source"]["commit"] != result["head"]
    assert result["unassessed_criteria"] == []


def test_unknown_operation_fails_closed():
    import pytest
    with pytest.raises(ValueError, match="Unsupported"):
        dispatch({"operation": "manual_accept", "args": {}})
