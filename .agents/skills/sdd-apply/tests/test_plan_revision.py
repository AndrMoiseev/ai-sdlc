from repository_support import accept_checkpoint
from lib.repository import repository
"""Plan revisions preserve accepted work and extend the remaining plan."""
from lib import artifact_storage as artifacts
from lib.state_storage import storage
from copy import deepcopy
from pathlib import Path

import pytest

from conftest import document, SPEC, Driver
from lib.common import digest, Rejected
from lib.inputs import spec_modules, validate
from lib.scheduler import available
from test_commits import prepared


def revise(project, names, modify=lambda tasks: None):
    change = project / "sdd/changes/demo"
    parser = spec_modules(SPEC)
    plan = parser.read_document(change / "tasks.md")
    existing = {t["id"]: t for t in plan.records}
    template = plan.records[0]
    tasks = []
    for number, name in enumerate(names, 1):
        task = deepcopy(existing.get("TASK-" + name, template))
        task.update(id="TASK-" + name, number=number, covers=["AC-" + name])
        task["verification"][0]["criteria"] = list(task["covers"])
        tasks.append(task)
    modify(tasks)
    document(change / "tasks.md", plan.meta, tasks)
    spec = parser.read_document(change / "specs/demo/spec.md")
    document(spec.path, spec.meta, [spec.records[0]] + [
        dict(sdd_record="acceptance", id="AC-" + name, requirement="REQ-one",
             conditions="Numbers", expected="Sum") for name in names
    ])
    decisions = parser.read_document(change / "review/decisions.md")
    for record in decisions.records:
        record["basis_commit"] = repository(project).head()
    document(decisions.path, decisions.meta, decisions.records)
    from repository_support import stage, commit
    stage(project, "sdd")
    commit(project, "Approved fixture revision")
    accept_checkpoint(project)


def accepted(driver, project):
    prepared(driver, project)
    driver.send("commit")
    driver.send("accept")
    driver.send("role_result", {"role_id": "verifier", "result": "DONE", "trace": "unit-test"})


def revised(driver):
    return driver.send("revised_plan", {"instruction": {
        "text": "Execute revised plan", "source": "fixture-user",
    }}, task_id=None)


def test_revision_preserves_accepted_and_revises_unfinished(project):
    revise(project, ["one", "two"])
    d = Driver(validate(project, "demo", {"text": "Execute", "source": "fixture"}, SPEC))
    accepted(d, project)
    completed = d.task
    d.send("checks_register", {"inventory": {"instructions": [], "ci": []}}, "TASK-two")
    d.send("worktree_create", {"workspace": str(project.parent / "task-worktrees")}, "TASK-two")
    d.send("role_register", {"role_id": "second-author", "kind": "executor",
        "context_id": "second-context", "fresh": True, "host": "codex",
        "launch_ref": "unit-test", "capabilities": {"fresh_context": True}}, "TASK-two")
    d.send("start", {"role_id": "second-author", "paths": ["second.txt"]}, "TASK-two")
    d.send("budget_extend", {"budget": "review", "limit": 4,
        "source": "fixture-user", "text": "Extra review"}, "TASK-two")
    d.send("role_result", {"role_id": "second-author", "result": "Conflict", "trace": "unit-test"}, "TASK-two")
    d.send("spec_conflict", {"reproduction": "New input unsupported", "criteria": ["AC-two"],
        "contract": "Revise remaining scope"}, "TASK-two")
    previous = d.state["run_id"]

    def modify(tasks):
        tasks[1]["verification"][0]["test_description"] = "Revised criterion"
        tasks[1]["depends_on"] = ["TASK-one"]
        tasks[2]["depends_on"] = ["TASK-two"]

    revise(project, ["one", "two", "three"], modify)
    result = revised(d)
    assert result["previous_run"] == previous
    assert d.task == completed
    assert d.state["tasks"]["TASK-two"]["plan"]["verification"][0]["test_description"] == "Revised criterion"
    assert d.state["tasks"]["TASK-two"]["review_limit"] == 4
    assert d.state["tasks"]["TASK-two"]["prior_result"]["status"] == "running"
    assert d.state["tasks"]["TASK-three"]["status"] == "pending"
    assert available(d.state) == ["TASK-two"]
    assert list(d.state["tasks"]) == ["TASK-one", "TASK-two", "TASK-three"]
    assert artifacts.exists(d.directory / "runs" / previous / "superseded-state.json")

    revise(project, ["one", "two", "three", "four"], modify)
    revised(d)
    assert d.task == completed
    assert d.state["tasks"]["TASK-two"]["review_limit"] == 4


@pytest.mark.parametrize("change", ["edit", "remove", "renumber"])
def test_revision_rejects_changes_to_accepted_atomically(execution_checkpoint, change):
    driver = execution_checkpoint("accepted")
    project = Path(driver.state["basis"]["project_root"])
    before = storage(driver.directory).read()
    runs = set(artifacts.paths(driver.directory / "runs"))
    if change == "edit":
        revise(project, ["one"], lambda tasks: tasks[0]["verification"][0].update(test_description="Changed"))
    elif change == "remove":
        revise(project, ["replacement"])
    else:
        revise(project, ["new", "one"])
    with pytest.raises(Rejected) as error:
        revised(driver)
    assert error.value.code == "completed_task_changed"
    assert storage(driver.directory).read() == before
    assert set(artifacts.paths(driver.directory / "runs")) == runs
    assert not artifacts.exists(driver.directory / "runs" / driver.state["run_id"] / "superseded-state.json")


@pytest.mark.parametrize("placement", ["number", "record"])
def test_revision_rejects_new_tasks_before_existing(driver, project, placement):
    def modify(tasks):
        if placement == "number":
            tasks[0]["number"], tasks[1]["number"] = 2, 1
        else:
            tasks.reverse()
    revise(project, ["one", "two"], modify)
    before = driver.state
    with pytest.raises(Rejected) as error:
        revised(driver)
    assert error.value.code == "new_tasks_append_only"
    assert driver.state == before


def test_revision_keeps_acceptance_but_requires_fresh_final_checks(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    project = Path(driver.state["basis"]["project_root"])
    driver.role("old-final", "final_verifier")
    driver.send("check_run", {"role_id": "old-final", "stage": "final"})
    driver.send("role_result", {"role_id": "old-final", "result": "DONE", "trace": "unit-test"})
    assert driver.send("finalize", task_id=None)["result"] == "complete"
    completed = driver.task
    # A changed normative document still requires final verification at the new basis.
    path = project / "sdd/changes/demo/design.md"
    path.write_bytes(path.read_bytes() + b"\nClarified design.\n")
    revise(project, ["one"])
    revised(driver)
    assert driver.task == completed
    from lib.verification import valid_evidence
    with pytest.raises(Rejected) as error:
        valid_evidence(driver.state, driver.task, driver.directory, "final")
    assert error.value.code == "required_checks"
    driver.role("new-final", "final_verifier")
    assert driver.send("check_run", {"role_id": "new-final", "stage": "final"})["outcome"] == "passed"
    assert driver.send("finalize", task_id=None)["result"] == "complete"


def stopped_completed_task(driver):
    """Seed consumed historical rounds; the real repair reducer produces the stop."""
    from lib.state import seal, save
    state = driver.state
    task = state["tasks"]["TASK-one"]
    task["review_rounds_started"] = task["review_limit"]
    task["review_rounds_completed"] = task["review_limit"]
    seal(state)
    save(driver.directory, state)
    result = driver.send("repair", {"reason": "Post-acceptance defect", "defect_evidence": "New project scenario fails"})
    assert result == {"blocked": "review_limit_reached"}
    assert driver.task["status"] == "accepted"


def followup_payload():
    return {"instruction": {"text": "Execute the approved new dependent task instead of reopening completed work", "source": "synthetic-user-message"},
            "completed_followups": [{"completed_task": "TASK-one", "followup_task": "TASK-two"}]}


def test_completed_followup_clears_only_obsolete_stop_preserving_task_and_budgets(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    stopped_completed_task(driver)
    completed = driver.task
    driver.send("block", {"reason": "external_service", "resume_condition": "Restore the service"}, task_id=None)
    project = Path(driver.state["basis"]["project_root"])
    revise(project, ["one", "two"], lambda tasks: tasks[1].update(depends_on=["TASK-one"]))
    previous = driver.state["run_id"]
    result = driver.send("revised_plan", followup_payload(), task_id=None)
    assert result["previous_run"] == previous
    assert driver.task == completed
    assert driver.task["review_rounds_started"] == driver.task["review_limit"]
    assert driver.state["tasks"]["TASK-two"]["status"] == "pending"
    assert driver.state["tasks"]["TASK-two"]["review_rounds_started"] == 0
    assert [block["reason"] for block in driver.state["blockers"]] == ["external_service"]
    resolved = result["resolved_completed_repairs"]
    assert resolved["mapping"] == followup_payload()["completed_followups"]
    assert resolved["removed_blockers"][0]["reason"] == "review_limit_reached"
    assert resolved["authorization"] == followup_payload()["instruction"]
    assert artifacts.exists(driver.directory / "runs" / previous / "superseded-state.json")


@pytest.mark.parametrize("invalid", ["existing", "unrelated", "unfinished", "active", "duplicate", "missing_stop", "missing_authorization"])
def test_completed_followup_rejects_invalid_mapping_before_archiving(execution_checkpoint, invalid):
    from lib.state import seal, save
    driver = execution_checkpoint("accepted")
    if invalid != "missing_stop":
        stopped_completed_task(driver)
    project = Path(driver.state["basis"]["project_root"])
    revise(project, ["one", "two"], lambda tasks: tasks[1].update(depends_on=[] if invalid == "unrelated" else ["TASK-one"]))
    payload = followup_payload()
    if invalid == "existing":
        payload["completed_followups"][0]["followup_task"] = "TASK-one"
    elif invalid == "duplicate":
        payload["completed_followups"] *= 2
    elif invalid in {"unfinished", "active"}:
        state = driver.state
        if invalid == "unfinished":
            state["tasks"]["TASK-one"]["status"] = "repairing"
        else:
            state["tasks"]["TASK-one"]["active_review"] = "unfinished-review"
        seal(state)
        save(driver.directory, state)
    elif invalid == "missing_authorization":
        payload.pop("instruction")
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("revised_plan", payload, task_id=None)
    assert error.value.code in {"completed_followup", "execution_instruction"}
    assert storage(driver.directory).read() == before
    assert not artifacts.exists(driver.directory / "runs" / driver.state["run_id"] / "superseded-state.json")


def test_followup_does_not_clear_unfinished_task_budget_stop(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    project = Path(driver.state["basis"]["project_root"])
    revise(project, ["one", "two"], lambda tasks: tasks[1].update(depends_on=["TASK-one"]))
    revised(driver)
    stopped_completed_task(driver)
    from lib.budgets import failure
    from lib.state import seal, save
    state = driver.state
    task = state["tasks"]["TASK-two"]
    task["test_repair_cycles_started"] = task["test_repair_limit"]
    failure(state, task, "test", "failed")
    save(driver.directory, seal(state))
    previous = driver.state["tasks"]["TASK-two"]
    revise(project, ["one", "two", "three"], lambda tasks: tasks[2].update(depends_on=["TASK-one"]))
    payload = followup_payload()
    payload["completed_followups"][0]["followup_task"] = "TASK-three"
    driver.send("revised_plan", payload, task_id=None)
    assert any(block["reason"] == "test_repair_limit_reached" and block["task_id"] == "TASK-two" for block in driver.state["blockers"])
    assert driver.state["tasks"]["TASK-two"]["test_repair_cycles_started"] == previous["test_repair_cycles_started"]
    assert driver.state["status"] == "blocked"
