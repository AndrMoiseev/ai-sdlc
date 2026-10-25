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
        for entry in record["inputs"]:
            entry["sha256"] = digest((change / entry["path"]).read_bytes())
    document(decisions.path, decisions.meta, decisions.records)


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
