from lib.api import dispatch
from test_commits import prepared


def test_full_sequential_lifecycle(driver, project):
    prepared(driver, project)
    driver.send("commit")
    driver.send("accept")
    driver.role("final-context", "final_verifier")
    assert driver.send("check_run", {"role_id": "final-context", "stage": "final"})["outcome"] == "passed"
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "complete"
    assert result["accepted_criteria"] == ["AC-one"]
    assert driver.state["status"] == "completed"
    view = dispatch({"operation": "dashboard", "args": {"directory": str(driver.directory)}})
    assert view["revision"] == driver.state["revision"]


def test_no_final_evidence_is_partial(driver, project):
    prepared(driver, project)
    driver.send("commit")
    driver.send("accept")
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "partial"
    assert result["missing"][0]["criteria"] == ["AC-one"]
    assert driver.state["status"] == "blocked"


def test_unknown_operation_fails_closed():
    import pytest
    with pytest.raises(ValueError, match="Unsupported"):
        dispatch({"operation": "manual_accept", "args": {}})
