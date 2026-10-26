from lib import artifact_storage as artifacts
from lib.repository import repository
from repository_support import stage as stage_files, commit
import sys
import json
from pathlib import Path
import pytest
from conftest import document, SPEC, Driver
from lib.common import digest
from lib.inputs import spec_modules, validate


@pytest.mark.parametrize("stage", ["baseline", "self", "independent", "final"])
def test_missing_command_location_blocks_even_when_command_passes(project, stage):
    # A broad command can succeed after its intended test has disappeared.
    reapprove(project, lambda t: t["verification"][0].update(run={"command": [sys.executable, "-B", "-c", "pass"]}))
    d = Driver(validate(project, "demo", {"text": "Execute", "source": "fixture"}, SPEC))
    if stage == "baseline":
        (project / "check.py").unlink()
        stage_files(project, "check.py")
        commit(project, "Baseline has missing verification location")
        d.start()
        outputs = d.task["baseline_checks"]["outputs"]
    else:
        d.start()
        if stage == "final":
            (d.root / "result.txt").write_text("implemented\n")
            d.freeze()
            d.verify()
            d.review()
            d.integrate()
            d.send("commit")
            d.send("accept")
            d.role("final", "final_verifier")
        (d.root / "check.py").unlink()
        if stage == "self":
            d.freeze()
            result = d.send("check_run", {"role_id": "author", "stage": stage})
        elif stage == "final":
            stage_files(project, "check.py")
            commit(project, "Final HEAD has missing verification location")
            result = d.send("check_run", {"role_id": "final", "stage": stage})
        else:
            d.freeze()
            result = d.verify()
        assert result["outcome"] == "unavailable"
        outputs = json.loads(artifacts.read_text(d.directory / result["log"]))["outputs"]
    assert outputs[0]["outcome"] == "unavailable"
    assert "exit_code" not in outputs[0]  # Do not execute an incomplete check.


def test_directory_location_is_relative_to_project_not_command_cwd(project):
    (project / "tests").mkdir()
    (project / "tests/check.py").write_text("assert True\n")
    stage_files(project, "tests")
    commit(project, "Existing verification directory")
    reapprove(project, lambda t: t["verification"][0].update(location="tests", run={"setup_required": "Create and run suite"}))
    d = Driver(validate(project, "demo", {"text": "Execute", "source": "fixture"}, SPEC))
    d.worktree()
    d.start()
    assert d.task["baseline_checks"]["outputs"][0]["outcome"] == "planned_absence"
    with pytest.raises(ValueError, match="argument array"):
        d.send("check_setup", {"check_id": "plan-1", "command": "python check.py", "cwd": "tests", "description": "Legacy setup"})
    assert d.task["checks"][0]["setup"] is None
    d.send("check_setup", {"check_id": "plan-1", "command": [sys.executable, "-B", "check.py"], "cwd": "tests", "description": "Prepared suite"})
    d.freeze()
    assert d.verify()["outcome"] == "passed"


def test_procedure_result_cannot_hide_missing_location(project):
    (project / "procedure.md").write_text("Inspect the check definition and verify the result.\n")
    stage_files(project, "procedure.md")
    commit(project, "Existing manual procedure")
    reapprove(project, lambda t: t["verification"][0].update(run={"procedure": "procedure.md"}))
    d = Driver(validate(project, "demo", {"text": "Execute", "source": "fixture"}, SPEC))
    d.worktree()
    d.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    d.role("author", "executor")
    d.send("start", {"role_id": "author", "paths": ["check.py"]})
    (d.root / "check.py").unlink()
    d.freeze()
    d.send("procedure_begin", {"check_id": "plan-1", "role_id": "author", "stage": "self"})
    d.send("procedure_result", {"check_id": "plan-1", "role_id": "author", "outcome": "passed", "steps": ["Synthetic observation"], "trace": "unit"})
    assert d.send("check_run", {"role_id": "author", "stage": "self"})["outcome"] == "unavailable"


def reapprove(project, modify):
    change = project / "sdd/changes/demo"
    parser = spec_modules(SPEC)
    doc = parser.read_document(change / "tasks.md")
    modify(doc.records[0])
    document(change / "tasks.md", doc.meta, doc.records)
    decisions = parser.read_document(change / "review/decisions.md")
    for record in decisions.records:
        if record["scope"]["stage"] == "plan_review":
            for entry in record["inputs"]:
                entry["sha256"] = digest((change / entry["path"]).read_bytes())
    document(change / "review/decisions.md", decisions.meta, decisions.records)
    stage_files(project, "sdd")
    commit(project, "Approved fixture plan revision")


def test_planned_setup_then_missing_runner_remains_blocker(project):
    def modify(task):
        task["verification"][0].update(location="new_check.py", run={"setup_required": "Create exact-output tests"})
    reapprove(project, modify)
    stage_files(project, "sdd")
    commit(project, "fixture planned setup approval")
    basis = validate(project, "demo", {"text": "Do it", "source": "fixture"}, SPEC)
    d = Driver(basis)
    d.start(["result.txt", "new_check.py"])
    original = (project / "sdd/changes/demo/tasks.md").read_bytes()
    (d.root / "new_check.py").write_text("assert 2 + 3 == 5\n")
    d.send("check_setup", {"check_id": "plan-1", "command": [sys.executable, "-B", "new_check.py"], "description": "Prepared planned assertions"})
    d.freeze()
    assert d.verify()["outcome"] == "passed"
    assert (project / "sdd/changes/demo/tasks.md").read_bytes() == original
    d.send("repair", {"reason": "reproduce lost runner", "defect_evidence": "fixture deletion"})
    (d.root / "new_check.py").unlink()
    d.freeze()
    assert d.verify()["outcome"] == "unavailable"
    assert d.state["status"] == "blocked"
    assert d.task["checks"][0]["setup"]["command"]


def test_linked_revision_preserves_counters_not_acceptance(basis, project):
    driver = Driver(basis)
    driver.send("budget_extend", {"budget": "review", "limit": 4, "source": "fixture-user", "text": "Extra review"})
    previous = driver.state["run_id"]
    reapprove(project, lambda task: task["verification"][0].update(test_description="Revised criterion detail"))
    result = driver.send("revised_plan", {"instruction": {"text": "Execute revised plan", "source": "fixture-user"}}, task_id=None)
    assert result["previous_run"] == previous
    assert result["run_id"] != previous
    assert driver.task["review_limit"] == 4
    assert driver.task["status"] == "pending"
    assert driver.state["mode"] == "parallel"
    assert driver.state["parallel_request"] == {"text": "Execute revised plan", "source": "fixture-user"}
    assert artifacts.exists(driver.directory / "runs" / previous / "superseded-state.json")


def test_procedure_requires_independent_performed_result(project):
    (project / "procedure.md").write_text("Check exact numeric addition and invalid input cases.\n")
    reapprove(project, lambda t: t["verification"][0].update(run={"procedure": "procedure.md"}))
    stage_files(project, "sdd", "procedure.md")
    commit(project, "approve fixture procedure")
    d = Driver(validate(project, "demo", {"text": "Execute", "source": "fixture"}, SPEC))
    d.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    d.role("author", "executor")
    d.role("baseline", "verifier")
    d.worktree()
    d.send("start", {"role_id": "author", "paths": ["result.txt"]})
    d.send("procedure_begin", {"check_id": "plan-1", "role_id": "baseline", "stage": "baseline"})
    d.send("procedure_result", {"check_id": "plan-1", "role_id": "baseline", "outcome": "passed", "steps": ["Synthetic fixture observation; not actual browser evidence"], "trace": "unit"})
    assert d.send("check_run", {"role_id": "baseline", "stage": "baseline"})["outcome"] == "baseline_recorded"
    d.freeze()
    d.role("verifier", "verifier")
    d.send("procedure_begin", {"check_id": "plan-1", "role_id": "verifier", "stage": "independent"})
    d.send("procedure_result", {"check_id": "plan-1", "role_id": "verifier", "outcome": "passed", "steps": ["Synthetic exact-output assertions"], "trace": "unit"})
    assert d.verify()["outcome"] == "passed"
    assert d.review()["status"] == "integrating"
