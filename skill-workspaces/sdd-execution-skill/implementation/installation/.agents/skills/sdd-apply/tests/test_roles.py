import pytest


def test_done_is_not_acceptance(driver):
    driver.start()
    driver.send("role_result", {"role_id": "author", "result": "DONE", "trace": "synthetic"})
    assert driver.task["status"] == "running"
    assert driver.task["commits"] == []


def test_context_independence_and_review(driver):
    driver.start()
    with pytest.raises(ValueError, match="share"):
        driver.role("fake-reviewer", "reviewer", "author")
    driver.freeze()
    driver.verify()
    assert driver.review()["status"] == "committing"
    assert driver.task["review_rounds_started"] == 1


def test_missing_host_capability(driver):
    with pytest.raises(ValueError, match="unavailable"):
        driver.send("role_register", {"role_id": "a", "kind": "executor", "context_id": "ctx", "fresh": True, "host": "codex", "launch_ref": "fixture", "capabilities": {"fresh_context": False}})
