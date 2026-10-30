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


def test_five_repairs_last_success(execution_checkpoint):
    driver = execution_checkpoint("started")
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


def test_budget_blocks_unrelated_event(execution_checkpoint):
    driver = execution_checkpoint("started")
    driver.send("block", {"reason": "test_repair_limit_reached", "resume_condition": "user decision"}, task_id=None)
    before = driver.state
    with pytest.raises(ValueError):
        driver.role("next", "reviewer")
    assert driver.state == before


def test_full_check_set_shares_deadline_including_report_capture(execution_checkpoint, monkeypatch):
    from lib import verification, explorer_assignments, check_evidence
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    command = driver.task["checks"][0]["run"]["command"]
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"],
        "additional": [{"id": name, "source": "review", "criteria": ["AC-one"], "run": {"command": command}}
                       for name in ("second", "third")]})
    clock, timeouts = [0.0], []
    original = verification.check_runner.run_command
    capture = check_evidence.capture_reports
    def run(command, cwd, timeout):
        timeouts.append(timeout)
        result = original(command, cwd, max(10, timeout))
        clock[0] += 4
        return result
    def reports(output, read_reports=True):
        result = capture(output, read_reports=read_reports)
        if read_reports:
            clock[0] += 2
        return result
    monkeypatch.setattr(explorer_assignments.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(verification.check_runner, "run_command", run)
    monkeypatch.setattr(check_evidence, "capture_reports", reports)
    driver.explorer("timed-explorer", "independent")
    result = driver.send("check_run", {"role_id": "timed-explorer", "stage": "independent", "timeout": 10})
    assert timeouts == [10, 4]
    assert result["outcome"] == "unavailable"
    assert driver.task["test_repair_cycles_started"] == 0
    assert [item["outcome"] for item in driver.task["evidence"][-3:]] == ["passed", "unavailable", "unavailable"]
    assert driver.state["status"] == "blocked"


def test_failed_retry_replacement_and_event_replay_preserve_budget(execution_checkpoint, monkeypatch):
    from lib.state import apply
    from lib import verification
    driver = execution_checkpoint("started")
    (driver.root / "check.py").write_text("assert False, 'defect'\n")
    driver.freeze()
    driver.explorer("first-explorer", "independent")
    state = driver.state
    event = {"event_id": "failed-batch", "run_id": state["run_id"], "expected_revision": state["revision"],
             "type": "check_run", "task_id": "TASK-one", "payload": {"role_id": "first-explorer", "stage": "independent"}}
    failed = apply(driver.directory, event)
    assert failed["outcome"] == "failed"
    def unexpected(*args):
        pytest.fail("Event replay executed a command")
    with monkeypatch.context() as patch:
        patch.setattr(verification.check_runner, "run_command", unexpected)
        assert apply(driver.directory, event) == failed
    driver.explorer("replacement-explorer", "independent")
    with pytest.raises(ValueError, match="reserve"):
        driver.send("check_run", {"role_id": "replacement-explorer", "stage": "independent"})
    assert driver.task["test_repair_cycles_started"] == 0
    driver.send("repair", {"reason": "Repair the observed defect"})
    (driver.root / "check.py").write_text("assert True\n")
    driver.freeze()
    assert driver.run_checks("independent")["outcome"] == "passed"
    assert driver.task["test_repair_cycles_started"] == 1
    assert driver.task["active_repair"] is None


def procedure_deadline_setup(execution_checkpoint):
    driver = execution_checkpoint("verified")
    check = {"id": "timed-procedure", "source": "fixture", "criteria": ["AC-one"],
             "execution_kind": "deterministic", "run": {"procedure": "check.py"}}
    driver.review(verdict="more_checks")
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [check]})
    return driver, "TASK-one", "independent"


def timed_explorer(driver, task_id, stage, ident, deadline=None):
    from lib.explorer_assignments import basis
    state = driver.state
    current = basis(state, state["tasks"].get(task_id), "checks", stage)
    assignment = {"id": ident, "kind": "checks", "stage": stage,
        "scope": {"project": state["basis"]["project_root"], "work": state["change_id"], "task": task_id},
        "basis": current, "read_scope": ["project"], "outputs": [str(driver.directory)],
        "check_ids": [check["id"] for check in current["checks"]], "registry_revision": current["registry_revision"],
        "limits": {"timeout": 10, **({"deadline": deadline} if deadline else {})}}
    driver.explorer(ident, stage, task_id=task_id, assignment=assignment)


@pytest.mark.parametrize("elapsed", [4, 11])
def test_procedure_and_commands_share_attempt_deadline(execution_checkpoint, monkeypatch, elapsed):
    from lib import explorer_assignments, verification, artifact_storage
    from lib.common import Rejected
    from lib.state_storage import storage
    import json
    driver, task_id, stage = procedure_deadline_setup(execution_checkpoint)
    clock = [1000.0]
    monkeypatch.setattr(explorer_assignments.time, "time", lambda: clock[0])
    monkeypatch.setattr(explorer_assignments.time, "monotonic", lambda: clock[0])
    timed_explorer(driver, task_id, stage, "procedure-explorer")
    attempt = driver.send("procedure_begin", {"role_id": "procedure-explorer", "stage": stage,
        "check_id": "timed-procedure"}, task_id=task_id)
    assert attempt["remaining_timeout"] == 10
    clock[0] += elapsed
    result = driver.send("procedure_result", {"role_id": "procedure-explorer", "check_id": "timed-procedure",
        "outcome": "passed", "steps": ["Synthetic deterministic observation"], "trace": "fake-clock adapter"}, task_id=task_id)
    assert result["outcome"] == ("passed" if elapsed < 10 else "unavailable")
    record = json.loads(artifact_storage.read_text(driver.directory / result["log"]))
    assert record["reported_outcome"] == "passed"
    if elapsed > 10:
        assert record["limitation"] == "check_deadline"
    timed_explorer(driver, task_id, stage, "aggregate-explorer")
    timeouts = []
    original = verification.check_runner.run_command
    def run(command, cwd, timeout):
        timeouts.append(timeout)
        return original(command, cwd, max(10, timeout))
    monkeypatch.setattr(verification.check_runner, "run_command", run)
    before = storage(driver.directory).read()
    aggregate = driver.send("check_run", {"role_id": "aggregate-explorer", "stage": stage}, task_id=task_id)
    assert aggregate["outcome"] == ("passed" if elapsed < 10 else "unavailable")
    assert timeouts == ([6] if elapsed < 10 else [])
    assert driver.task["test_repair_cycles_started"] == 0
    if elapsed < 10:
        clock[0] += 7
        before = storage(driver.directory).read()
        with pytest.raises(Rejected) as error:
            driver.send("procedure_begin", {"role_id": "aggregate-explorer", "stage": stage,
                "check_id": "timed-procedure"}, task_id=task_id)
        assert error.value.code == "check_deadline"
        assert storage(driver.directory).read() == before


def test_expired_assignment_cannot_begin_procedure(execution_checkpoint, monkeypatch):
    from lib import explorer_assignments
    from lib.common import Rejected
    from lib.state_storage import storage
    driver, task_id, stage = procedure_deadline_setup(execution_checkpoint)
    monkeypatch.setattr(explorer_assignments.time, "time", lambda: 1000.0)
    timed_explorer(driver, task_id, stage, "expired-explorer", "1970-01-01T00:00:01+00:00")
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("procedure_begin", {"role_id": "expired-explorer", "stage": stage,
            "check_id": "timed-procedure"}, task_id=task_id)
    assert error.value.code == "check_deadline"
    assert storage(driver.directory).read() == before


def test_reserved_procedure_repair_receives_new_attempt_budget(execution_checkpoint, monkeypatch):
    from lib import explorer_assignments
    from lib.common import Rejected
    driver, task_id, stage = procedure_deadline_setup(execution_checkpoint)
    clock = [1000.0]
    monkeypatch.setattr(explorer_assignments.time, "time", lambda: clock[0])
    monkeypatch.setattr(explorer_assignments.time, "monotonic", lambda: clock[0])
    timed_explorer(driver, task_id, stage, "first-procedure")
    payload = {"role_id": "first-procedure", "stage": stage, "check_id": "timed-procedure"}
    driver.send("procedure_begin", payload)
    clock[0] += 11
    result = driver.send("procedure_result", {"role_id": "first-procedure", "check_id": "timed-procedure",
        "outcome": "passed", "steps": ["Observed after deadline"], "trace": "fake-clock adapter"})
    assert result["outcome"] == "unavailable"
    timed_explorer(driver, task_id, stage, "replacement-procedure")
    with pytest.raises(Rejected) as error:
        driver.send("procedure_begin", {**payload, "role_id": "replacement-procedure"})
    assert error.value.code == "repair_cycle_required"
    driver.send("repair", {"reason": "Restore procedure timing", "defect_evidence": result["log"], "test_failure": True})
    driver.freeze()
    timed_explorer(driver, task_id, stage, "repaired-procedure")
    fresh = driver.send("procedure_begin", {**payload, "role_id": "repaired-procedure"})
    assert fresh["remaining_timeout"] == 10
    assert driver.task["test_repair_cycles_started"] == 1
    result = driver.send("procedure_result", {"role_id": "repaired-procedure", "check_id": "timed-procedure",
        "outcome": "passed", "steps": ["Completed within new allowance"], "trace": "fake-clock adapter"})
    assert result["outcome"] == "passed"
    assert driver.send("check_run", {"role_id": "repaired-procedure", "stage": stage})["outcome"] == "passed"
    assert driver.task["test_repair_cycles_started"] == 1
    assert driver.task["active_repair"] is None
