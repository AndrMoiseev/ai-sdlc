from copy import deepcopy
import pytest
from lib.budgets import reserve_review, failure, extend, repair


def test_third_success_and_fourth_blocks(driver):
    state = driver.state
    task = state["tasks"]["TASK-one"]
    for i in range(3):
        assert reserve_review(state, task, str(i))
        task["active_review"] = None
    assert state["status"] == "active"
    assert not reserve_review(state, task, "four")
    assert state["status"] == "blocked"
    extend(state, task, {"budget": "review", "limit": 4, "source": "user-msg", "text": "One extra"})
    assert state["status"] == "active"
    assert task["test_repair_limit"] == 5


def test_five_repairs_last_success(driver):
    driver.start()
    state = driver.state
    task = state["tasks"]["TASK-one"]
    task["last_check_failed"] = True
    failure(state, task, "test", "failed")
    for i in range(5):
        repair(state, task, {"reason": "fix"})
        assert task["test_repair_cycles_started"] == i + 1
        with pytest.raises(ValueError, match="existing"):
            repair(state, task, {"reason": "double"})
        task["active_repair"] = None
    assert state["status"] == "active"
    failure(state, task, "test", "failed")
    assert state["blockers"][0]["reason"] == "test_repair_limit_reached"
    extend(state, task, {"budget": "test", "limit": 6, "source": "msg", "text": "Extra cycle"})
    assert task["review_limit"] == 3


def test_budget_blocks_unrelated_event(driver):
    driver.start()
    driver.send("block", {"reason": "test_repair_limit_reached", "resume_condition": "user decision"}, task_id=None)
    before = driver.state
    with pytest.raises(ValueError):
        driver.role("next", "reviewer")
    assert driver.state == before
