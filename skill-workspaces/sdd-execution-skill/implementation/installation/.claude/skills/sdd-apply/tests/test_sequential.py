from copy import deepcopy
from lib.scheduler import available


def test_default_one_cycle_and_blocked_stop(driver):
    state = driver.state
    task = deepcopy(state["tasks"]["TASK-one"])
    task["plan"].update(id="TASK-two", number=2)
    state["tasks"]["TASK-two"] = task
    assert available(state) == ["TASK-one"]
    state["tasks"]["TASK-one"]["status"] = "running"
    assert available(state) == []
    state["tasks"]["TASK-one"]["status"] = "blocked"
    assert available(state) == []
    state["tasks"]["TASK-one"]["status"] = "accepted"
    assert available(state) == ["TASK-two"]


def test_dependency_needs_accepted(driver):
    state = driver.state
    state["mode"] = "parallel"
    task = deepcopy(state["tasks"]["TASK-one"])
    task["plan"].update(id="TASK-two", number=2, depends_on=["TASK-one"])
    state["tasks"]["TASK-two"] = task
    assert available(state) == ["TASK-one"]
    state["tasks"]["TASK-one"]["status"] = "committing"
    assert available(state) == []
