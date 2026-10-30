"""Criterion/gate matrices use existing memory repository and artifact adapters."""
import json

import pytest

from lib import artifact_storage as artifacts
from lib.common import Rejected
from lib.verification_results import packet, require_passed


def payload(driver, role="verifier", outcome="passed"):
    state = driver.state
    context = packet(state, state["tasks"]["TASK-one"], driver.directory)
    criteria = context.pop("criteria")
    return {**context, "role_id": role, "criteria_results": [
        {"criterion_id": criterion, "outcome": outcome,
         "reason": "Fixture source and arithmetic assertion inspected", "references": ["check.py:1"]}
        for criterion in criteria], "limitations": [], "trace": "synthetic verifier trace"}


def executed(execution_checkpoint):
    # Each negative submission restores real, independently serialized evidence.
    # Only conclusion inputs/artifacts vary; no command-side mutation is tested.
    return execution_checkpoint("executed", memory_worktree=True)


@pytest.mark.parametrize("operation,checkpoint", [
    ("review_start", "verified"), ("transfer", "worktree-reviewed"),
    ("commit", "reviewed"), ("accept", "reviewed")])
@pytest.mark.parametrize("conclusion", ["missing", "failed", "unavailable"])
def test_every_task_gate_requires_positive_conclusion(execution_checkpoint, operation, checkpoint, conclusion):
    from lib.transitions import reduce
    driver = execution_checkpoint(checkpoint, memory_worktree=True)
    state = driver.state
    task = state["tasks"]["TASK-one"]
    if operation == "review_start":
        driver.role("gate-reviewer", "reviewer")
        state = driver.state
        task = state["tasks"]["TASK-one"]
    if conclusion == "missing":
        task["verification_results"] = []
    else:
        task["verification_results"][-1]["outcome"] = conclusion
        task["verification_results"][-1]["criteria_results"][0]["outcome"] = conclusion
    with pytest.raises(Rejected) as error:
        reduce(state, {"type": operation, "task_id": "TASK-one", "event_id": "gate-test",
                       "payload": {"role_id": "gate-reviewer"}}, driver.directory)
    assert error.value.code == ("verification_missing" if conclusion == "missing" else "verification_failed")


@pytest.mark.parametrize("damage,code", [
    ("missing", "verification_criteria"), ("duplicate", "verification_criteria"),
    ("foreign", "verification_criteria"), ("empty_reason", "verification_criteria"),
    ("empty_references", "verification_criteria"), ("basis", "verification_basis"),
    ("registry", "verification_basis"), ("stage", "verification_stage"),
    ("evidence", "verification_evidence"), ("digest", "verification_evidence"),
    ("summary", "verification_evidence")])
def test_conclusion_rejects_incomplete_foreign_and_stale_inputs(execution_checkpoint, damage, code):
    driver = executed(execution_checkpoint)
    value = payload(driver)
    if damage == "missing":
        value["criteria_results"] = []
    elif damage == "duplicate":
        value["criteria_results"] *= 2
    elif damage == "foreign":
        value["criteria_results"][0]["criterion_id"] = "AC-other-task"
    elif damage == "empty_reason":
        value["criteria_results"][0]["reason"] = " "
    elif damage == "empty_references":
        value["criteria_results"][0]["references"] = []
    elif damage == "basis":
        value["basis"]["source"]["commit"] = "f" * 40
    elif damage == "registry":
        value["basis"]["registry_revision"] += 1
    elif damage == "stage":
        value["stage"] = "self"
    elif damage == "evidence":
        value["evidence_refs"] = []
    elif damage == "digest":
        value["evidence_refs"][0]["sha256"] = "0" * 64
    else:
        value["evidence_refs"][0]["summary"]["sha256"] = "0" * 64
    with pytest.raises(Rejected) as error:
        driver.send("verification_result", value)
    assert error.value.code == code
    assert driver.task["verification_results"] == []


@pytest.mark.parametrize("kind", ["executor", "explorer", "reviewer", "foreign-verifier"])
def test_only_active_independent_task_verifier_can_conclude(execution_checkpoint, kind):
    from lib.verification_results import transition
    driver = executed(execution_checkpoint)
    state = driver.state
    role = state["roles"]["verifier"]
    if kind == "foreign-verifier":
        role["task_id"] = "TASK-other"
    else:
        role["kind"] = kind
    with pytest.raises(Rejected) as error:
        transition(state, state["tasks"]["TASK-one"],
                   {"event_id": "foreign-conclusion", "payload": payload(driver)}, driver.directory)
    assert error.value.code == "role_unavailable"


@pytest.mark.parametrize("damage", ["author_context", "finished", "not_fresh"])
def test_verifier_identity_is_checked_at_submission(execution_checkpoint, damage):
    from lib.verification_results import transition
    driver = executed(execution_checkpoint)
    state = driver.state
    role = state["roles"]["verifier"]
    role[{"author_context": "context_id", "finished": "status", "not_fresh": "fresh"}[damage]] = {
        "author_context": "author", "finished": "finished", "not_fresh": False}[damage]
    with pytest.raises(Rejected) as error:
        transition(state, state["tasks"]["TASK-one"],
                   {"event_id": "identity-conclusion", "payload": payload(driver)}, driver.directory)
    assert error.value.code == ("role_unavailable" if damage == "finished" else "role_not_independent")


def test_role_result_and_self_do_not_supply_conclusion(execution_checkpoint):
    driver = execution_checkpoint("frozen")
    driver.role("verifier", "verifier")
    assert driver.run_checks("self")["outcome"] == "passed"
    with pytest.raises(Rejected, match="Every required"):
        driver.send("verification_result", payload(driver))
    assert driver.run_checks("independent")["outcome"] == "passed"
    driver.send("role_result", {"role_id": "verifier", "result": "passed", "trace": "unit"})
    driver.role("reviewer", "reviewer")
    with pytest.raises(Rejected, match="verifier conclusion"):
        driver.send("review_start", {"role_id": "reviewer"})


@pytest.mark.parametrize("outcome", ["failed", "unavailable"])
def test_negative_conclusion_preserves_green_execution_and_budgets(execution_checkpoint, outcome):
    driver = executed(execution_checkpoint)
    before = driver.task
    result = driver.conclude(outcome=outcome, check_request="Check subtraction at the public API")
    assert result["verification_result"]["outcome"] == outcome
    assert driver.task["evidence"] == before["evidence"]
    assert driver.task["test_repair_cycles_started"] == driver.task["review_rounds_started"] == 0
    assert driver.task["last_check_failed"] is False
    assert driver.state["status"] == "active"
    with pytest.raises(Rejected, match="passed conclusion"):
        require_passed(driver.state, driver.task, driver.directory)


def test_latest_conclusion_and_new_attempt_invalidate_old_pass(execution_checkpoint):
    driver = execution_checkpoint("verified")
    first = driver.task["verification_results"][-1]
    driver.conclude(outcome="failed", check_request="Add the missing boundary assertion")
    with pytest.raises(Rejected, match="passed conclusion"):
        require_passed(driver.state, driver.task, driver.directory)
    driver.conclude()
    assert require_passed(driver.state, driver.task, driver.directory)
    assert driver.run_checks("independent")["outcome"] == "passed"
    with pytest.raises(Rejected, match="attempt changed"):
        require_passed(driver.state, driver.task, driver.directory)
    driver.conclude()
    assert require_passed(driver.state, driver.task, driver.directory)
    assert driver.task["verification_results"][0] == first


def test_new_failed_attempt_cannot_select_old_pass(execution_checkpoint, monkeypatch):
    from lib import verification
    driver = execution_checkpoint("verified")
    original = verification.check_runner.run_command
    def failed(*args):
        return {**original(*args), "outcome": "failed", "exit_code": 7}
    monkeypatch.setattr(verification.check_runner, "run_command", failed)
    assert driver.run_checks("independent")["outcome"] == "failed"
    with pytest.raises(Rejected, match="Latest required check"):
        require_passed(driver.state, driver.task, driver.directory)
    assert driver.conclude(outcome="failed")["verification_result"]["outcome"] == "failed"


def test_unavailable_report_can_receive_negative_conclusion_while_run_is_blocked(execution_checkpoint):
    driver = execution_checkpoint("verified")
    gap = driver.conclude(outcome="unavailable", check_request="Capture the required structured report")
    driver.send("checks_extend", {"verification_result": gap["verification_result"]["id"], "additional": [
        {"id": "report", "source": "gap", "criteria": ["AC-one"], "run": driver.task["checks"][0]["run"],
         "configuration": {"structured_reports": [{"format": "pytest-junit", "path": "missing.xml", "required": True}]}}]})
    assert driver.run_checks("independent")["outcome"] == "unavailable"
    assert driver.state["status"] == "blocked"
    conclusion = driver.conclude(outcome="unavailable")
    assert conclusion["verification_result"]["outcome"] == "unavailable"
    assert driver.task["test_repair_cycles_started"] == 0
    with pytest.raises(Rejected, match="Latest required check"):
        require_passed(driver.state, driver.task, driver.directory)


@pytest.mark.parametrize("damage", ["source", "manifest", "configuration", "registry", "pending_procedure"])
def test_current_basis_and_attempt_changes_invalidate_conclusion(execution_checkpoint, damage):
    from lib.verification_results import applicable
    driver = execution_checkpoint("verified")
    state = driver.state
    task = state["tasks"]["TASK-one"]
    if damage == "source":
        task["verification_results"][-1]["basis"]["source"]["commit"] = "0" * 40
    elif damage == "manifest":
        task["verification_results"][-1]["basis"]["manifest"] = "0" * 64
    elif damage == "configuration":
        task["checks"][0]["configuration"] = {"setting": "changed"}
    elif damage == "registry":
        task["check_registry"]["revision"] += 1
    else:
        task["procedures"] = {"plan-1": {"stage": "independent", "role_id": "verifier"}}
    with pytest.raises(Rejected) as error:
        applicable(state, task, driver.directory)
    assert error.value.code == "verification_stale"


@pytest.mark.parametrize("when", ["submission", "gate"])
def test_raw_artifact_corruption_blocks_conclusion_use(execution_checkpoint, when):
    from lib.state_objects import StateObjects
    driver = executed(execution_checkpoint)
    value = payload(driver)
    if when == "gate":
        driver.send("verification_result", value)
    record = json.loads(artifacts.read_text(driver.directory / value["evidence_refs"][0]["log"]))
    machine = StateObjects(driver.directory).get(record["outputs"][0]["summary"])
    artifacts.write(driver.directory / machine["artifacts"]["stdout"]["path"], "changed raw bytes")
    with pytest.raises(Rejected):
        if when == "submission":
            driver.send("verification_result", value)
        else:
            require_passed(driver.state, driver.task, driver.directory)


def test_integration_preserves_original_evidence_without_running_checks(execution_checkpoint, monkeypatch):
    from lib import verification
    driver = execution_checkpoint("worktree-reviewed")
    evidence = driver.task["evidence"]
    conclusions = driver.task["verification_results"]
    roles = driver.task["roles"]
    def unexpected(*args, **kwargs):
        pytest.fail("Transfer must not execute checks again")
    monkeypatch.setattr(verification.check_runner, "run_command", unexpected)
    driver.send("transfer")
    driver.send("integrate")
    driver.send("candidate")
    assert driver.task["status"] == "committing"
    assert driver.task["review_rounds_started"] == 1
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"
    assert driver.task["evidence"] == evidence
    assert driver.task["verification_results"] == conclusions
    assert driver.task["roles"] == roles
    assert conclusions[-1]["basis"]["source"]["commit"] == driver.task["transfer"]["commit"]
    from lib.state_view import check_progress
    proof = check_progress(driver.state, driver.task, "independent")
    assert proof["execution"]["status"] == proof["conclusion"]["status"] == "passed"
