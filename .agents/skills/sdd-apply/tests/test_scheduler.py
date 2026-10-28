from copy import deepcopy
from lib.scheduler import available


def test_independent_task_remains_available_when_another_is_running_or_blocked(driver):
    state = driver.state
    task = deepcopy(state["tasks"]["TASK-one"])
    task["plan"].update(id="TASK-two", number=2)
    state["tasks"]["TASK-two"] = task
    assert available(state) == ["TASK-one", "TASK-two"]
    state["tasks"]["TASK-one"]["status"] = "running"
    assert available(state) == ["TASK-two"]
    state["tasks"]["TASK-one"]["status"] = "blocked"
    assert available(state) == ["TASK-two"]
    state["tasks"]["TASK-one"]["status"] = "accepted"
    assert available(state) == ["TASK-two"]


def test_dependency_needs_accepted(driver):
    state = driver.state
    task = deepcopy(state["tasks"]["TASK-one"])
    task["plan"].update(id="TASK-two", number=2, depends_on=["TASK-one"])
    state["tasks"]["TASK-two"] = task
    assert available(state) == ["TASK-one"]
    state["tasks"]["TASK-one"]["status"] = "committing"
    assert available(state) == []
    # An earlier task number cannot bypass an unaccepted dependency.
    state["tasks"]["TASK-one"]["plan"]["number"] = 3
    assert available(state) == []
    state["tasks"]["TASK-one"]["status"] = "accepted"
    assert available(state) == ["TASK-two"]
