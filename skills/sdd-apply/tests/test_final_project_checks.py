"""Ordinary final project checks through the real reducer; host traces are synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from lib import artifact_storage as artifacts
from lib.common import Rejected, digest
from lib.dashboard import projection, render
from lib.final_checks import evidence
from lib.state_view import compact
from lib.state_storage import storage
from repository_support import stage, commit, write_file


COMMAND = [sys.executable, "-B", "-c",
           "from pathlib import Path; assert Path('result.txt').read_text() == 'verified result\\n'; assert 2 + 3 == 5"]


def register(driver, run=None, **fields):
    check = {"id": "project-result", "criteria": ["AC-one"], "source": "Project release instructions",
             "run": run or {"command": COMMAND}, **fields}
    return driver.send("checks_register", {"inventory": {"instructions": ["release instructions"], "ci": []},
                                           "additional": [check]}, task_id=None)


def final_role(driver, ident="project-final", **fields):
    return driver.send("role_register", {"role_id": ident, "kind": "final_verifier", "context_id": ident,
        "fresh": True, "host": "codex", "launch_ref": "synthetic-unit-test",
        "capabilities": {"fresh_context": True}, **fields}, task_id=None)


def run_final(driver, role="project-final", stage="final"):
    return driver.send("check_run", {"role_id": role, "stage": stage}, task_id=None)


def task_final(driver):
    driver.role("task-final", "final_verifier")
    assert driver.send("check_run", {"role_id": "task-final", "stage": "final"})["outcome"] == "passed"


@pytest.fixture(scope="session")
def final_project_checkpoints(execution_checkpoints, repository_seeds):
    from checkpoints import LazyCheckpoints
    from memory_repository import MemoryRepositories
    branches = {}

    def checkpoint(procedure=False, task_checks=True):
        # Build lazily after the function-scoped CLI adapters have been installed.
        if procedure not in branches:
            backend = MemoryRepositories(repository_seeds)

            def steps():
                driver = execution_checkpoints["accepted"].restore(backend, branch.states)
                if procedure:
                    root = Path(driver.state["basis"]["project_root"])
                    (root / "release.md").write_text("Check result.txt equals verified result followed by a newline. Record the command and outcome.\n")
                    stage(root, "release.md")
                    commit(root, "Add project release procedure")
                    from repository_support import accept_execution_source
                    accept_execution_source(driver)
                register(driver, {"procedure": "release.md"} if procedure else None)
                final_role(driver)
                yield "registered", driver
                task_final(driver)
                yield "task-verified", driver

            branch = LazyCheckpoints(execution_checkpoints.workspace, backend, steps())
            branches[procedure] = branch
        return branches[procedure]["task-verified" if task_checks else "registered"]

    return checkpoint


@pytest.fixture
def prepared_project(final_project_checkpoints, repository_backend, state_backend):
    return lambda memory_worktree=True, **options: final_project_checkpoints(**options).restore(
        repository_backend, state_backend, memory_worktree=memory_worktree)


def begin(driver, role="project-final"):
    return driver.send("procedure_begin", {"check_id": "project-result", "role_id": role, "stage": "final"}, task_id=None)


def finish(driver, role="project-final", outcome="passed"):
    from lib.inputs import spec_modules
    run_command = spec_modules("check_runner").run_command
    output = run_command(COMMAND, Path(driver.state["basis"]["project_root"]), 30)
    assert output["outcome"] == "passed"
    return driver.send("procedure_result", {"check_id": "project-result", "role_id": role, "outcome": outcome,
        "steps": [{"command_execution": output, "observation": outcome}], "trace": "synthetic-unit-test actual fixture assertion"}, task_id=None)


def log(driver, result):
    return json.loads(artifacts.read_text(driver.directory / result["log"]))


def test_additional_registry_preserves_task_contract_and_requires_both_finals(prepared_project):
    driver = prepared_project(task_checks=False, memory_worktree=False)
    before = deepcopy(driver.task)
    result = run_final(driver)
    assert result["outcome"] == "passed"
    assert driver.task == before
    record = log(driver, result)
    assert record["task_id"] is None and record["stage"] == "final"
    assert record["basis"]["work_kind"] == "change"
    assert record["basis"]["task_checks"] == {"TASK-one": driver.task["checks"]}
    assert [item["check_id"] for item in record["outputs"]] == ["project-result"]
    # Project proof cannot replace the ordinary task-scoped final evidence.
    assert driver.send("finalize", task_id=None)["result"] == "partial"
    driver.send("resume", {"host_trace": "synthetic-unit-test", "live_contexts": ["project-final"],
        "resolutions": [{"reason": "final_incomplete", "task_id": None, "evidence": "Task final verification is still required"}]}, task_id=None)
    task_final(driver)
    result = driver.send("finalize", task_id=None)
    assert result["result"] == "complete" and result["accepted_criteria"] == ["AC-one"]
    assert result["project_checks"]["gaps"] == []


def test_missing_required_final_report_preserves_exit_and_blocks_completion(execution_checkpoint):
    from lib.state import read_object
    driver = execution_checkpoint("accepted")
    register(driver, configuration={"structured_reports": [
        {"format": "pytest-junit", "path": "missing-final.xml", "required": True}]})
    final_role(driver)
    task_final(driver)
    result = run_final(driver)
    assert result["outcome"] == "failed" and result["failures"] == ["project-result"]
    assert result["summary"]["evidence_complete"] is False
    output = log(driver, result)["outputs"][0]
    assert output["exit_code"] == 0 and output["outcome"] == "passed"
    summary = read_object(driver.directory, output["summary"])
    assert summary["task_id"] is None and summary["stage"] == "final"
    assert summary["structured_reports"][0]["error"]
    assert driver.send("finalize", task_id=None)["result"] == "partial"


def test_missing_project_evidence_blocks_complete_after_task_final(prepared_project):
    driver = prepared_project()
    final = driver.send("finalize", task_id=None)
    assert final["result"] == "partial" and final["accepted_criteria"] == []
    assert final["missing"][0]["reason"] == "final_evidence_missing"


def test_ordinary_without_additional_registry_keeps_original_final_contract(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    task_final(driver)
    assert "final_project_checks" not in compact(driver.state)
    assert driver.send("finalize", task_id=None)["result"] == "complete"
    assert "final_checks" not in driver.state


def test_register_requires_accepted_integrated_tasks(driver):
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        register(driver)
    assert error.value.code == "final_tasks"
    assert storage(driver.directory).read() == before


@pytest.mark.parametrize("stage", ["baseline", "self", "independent", "integration"])
def test_project_registry_runs_only_at_final(prepared_project, stage):
    driver = prepared_project()
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        run_final(driver, stage=stage)
    assert error.value.code == "check_stage"
    assert storage(driver.directory).read() == before


@pytest.mark.parametrize("fields", [{"criteria": ["AC-unknown"]}, {"run": {"setup_required": "invent new check"}},
                                     {"run": {"command": "python check.py"}}, {"run": {"procedure": "../escape.md"}}])
def test_final_registry_rejects_unapproved_or_unexecutable_contracts(execution_checkpoint, fields):
    driver = execution_checkpoint("accepted")
    before = storage(driver.directory).read()
    with pytest.raises(Rejected):
        register(driver, **fields)
    assert storage(driver.directory).read() == before


def test_project_role_is_fresh_independent_and_run_scoped(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    register(driver)
    for fields in ({"context_id": "author"}, {"kind": "executor"}, {"fresh": False}):
        before = storage(driver.directory).read()
        with pytest.raises(Rejected):
            final_role(driver, **fields)
        assert storage(driver.directory).read() == before
    driver.role("task-final", "final_verifier")
    with pytest.raises(Rejected) as error:
        run_final(driver, "task-final")
    assert error.value.code == "final_role"
    packet = final_role(driver)
    contents = json.loads(artifacts.read_text(Path(packet["packet"])))
    assert contents["task"] is None and contents["work_kind"] == "change"
    assert set(contents["criteria"]) == {"AC-one"}
    assert contents["tasks"]["TASK-one"]["status"] == "accepted"


@pytest.mark.parametrize("missing", [False, True])
def test_failed_or_unavailable_project_check_blocks_retry_and_completion(execution_checkpoint, missing):
    driver = execution_checkpoint("accepted")
    register(driver, {"command": COMMAND if missing else [sys.executable, "-B", "-c", "assert 2 + 3 == 6"]},
             **({"location": "missing.py"} if missing else {}))
    final_role(driver)
    task_final(driver)
    result = run_final(driver)
    assert result["outcome"] == "failed" and result["failures"] == ["project-result"]
    assert log(driver, result)["outputs"][0]["outcome"] == ("unavailable" if missing else "failed")
    with pytest.raises(Rejected) as error:
        run_final(driver)
    assert error.value.code == "repair_owner_required"
    assert driver.send("finalize", task_id=None)["result"] == "partial"


@pytest.mark.parametrize("drift", ["head", "manifest", "registry", "task_checks", "work_kind", "change_id", "run_id"])
def test_project_evidence_binds_full_current_identity(prepared_project, drift):
    driver = prepared_project()
    assert run_final(driver)["outcome"] == "passed"
    state = driver.state
    if drift == "head":
        root = Path(state["basis"]["project_root"])
        write_file(root, "new.txt", b"New integrated content\n")
        stage(root, "new.txt")
        commit(root, "Change final HEAD")
    elif drift == "manifest":
        state["basis"]["head"] = "0" * 40
    elif drift == "registry":
        registry = state["final_checks"]
        registry["revision"] += 1
        registry["history"].append({"revision": registry["revision"], "event_id": "changed", "checks": deepcopy(registry["checks"])})
    elif drift == "task_checks":
        state["tasks"]["TASK-one"]["checks"][0]["configuration"] = {"changed": True}
    elif drift == "work_kind":
        # Alter a saved evidence identity, without inventing refactoring documents.
        state["final_checks"]["evidence"][-1]["basis"]["work_kind"] = "refactoring"
    else:
        state[drift] = "foreign-work"
    _, matches, gaps = evidence(state, driver.directory)
    assert matches == [] and gaps[0]["reason"] == "final_evidence_missing"


@pytest.mark.parametrize("corruption", ["command", "role", "outcome", "cwd", "configuration"])
def test_unrelated_or_tampered_log_does_not_prove_project_check(prepared_project, corruption):
    driver = prepared_project()
    result = run_final(driver)
    record = log(driver, result)
    if corruption == "command":
        record["outputs"][0]["command"] = [sys.executable, "-B", "-c", "pass"]
    elif corruption == "role":
        record["role_id"] = "author"
    elif corruption in {"cwd", "configuration"}:
        record["outputs"][0][corruption] = "foreign-configuration"
    else:
        record["outputs"][0]["outcome"] = "failed"
    path = driver.directory / result["log"]
    artifacts.write(path, json.dumps(record))
    state = driver.state
    for item in state["final_checks"]["evidence"]:
        item["log_hash"] = digest(artifacts.read_bytes(path))
    with pytest.raises(Rejected) as error:
        evidence(state, driver.directory)
    assert error.value.code in {"evidence_command", "evidence_basis"}


@pytest.mark.parametrize("outcome", ["pending", "passed", "failed", "unavailable", "skipped", "unstable"])
def test_latest_procedure_attempt_supersedes_same_basis_pass(prepared_project, outcome):
    driver = prepared_project(procedure=True)
    begin(driver)
    previous = finish(driver)
    assert run_final(driver)["outcome"] == "passed"
    attempt = begin(driver)
    assert attempt["basis"] == previous["basis"] and attempt["attempt_id"] != previous["attempt_id"]
    if outcome != "pending":
        finish(driver, outcome=outcome)
    _, matches, gaps = evidence(driver.state, driver.directory)
    assert matches == []
    assert gaps[0]["reason"] == ({"pending": "procedure_pending", "passed": "procedure_superseded"}.get(outcome, outcome))
    if outcome == "passed":
        assert run_final(driver)["outcome"] == "passed"
        assert driver.send("finalize", task_id=None)["result"] == "complete"
    else:
        assert driver.send("finalize", task_id=None)["result"] == "partial"


def test_lost_final_verifier_archives_pending_procedure_and_requires_fresh_attempt(prepared_project):
    driver = prepared_project(procedure=True)
    begin(driver)
    finish(driver)
    assert run_final(driver)["outcome"] == "passed"
    interrupted = begin(driver)
    live = [role["context_id"] for role in driver.state["roles"].values()
            if role["status"] == "active" and role["role_id"] != "project-final"]
    driver.send("resume", {"host_trace": "synthetic-unit-test lost context", "live_contexts": live}, task_id=None)
    final_role(driver, "successor", successor_of="project-final")
    resolution = {"reason": "lost_role", "task_id": None, "role_id": "project-final", "successor": "successor",
                  "evidence": "Interrupted procedure must be executed by successor"}
    payload = {"host_trace": "synthetic-unit-test fresh successor", "live_contexts": live + ["successor"], "resolutions": [resolution]}
    with pytest.raises(Rejected) as error:
        driver.send("resume", payload, task_id=None)
    assert error.value.code == "procedure_reconciliation"
    resolution["abandon_procedures"] = ["project-result"]
    assert driver.send("resume", payload, task_id=None)["status"] == "active"
    abandoned = driver.state["final_checks"]["evidence"][-1]
    assert abandoned["outcome"] == "abandoned" and abandoned["attempt_id"] == interrupted["attempt_id"]
    assert evidence(driver.state, driver.directory)[1] == []
    with pytest.raises(Rejected) as error:
        finish(driver, "successor")
    assert error.value.code == "procedure_owner"
    begin(driver, "successor")
    finish(driver, "successor")
    assert run_final(driver, "successor")["outcome"] == "passed"
    assert driver.send("finalize", task_id=None)["result"] == "complete"


def test_project_progress_is_distinct_from_task_acceptance(prepared_project):
    driver = prepared_project()
    data = projection(driver.state)
    assert data["accepted"] == data["total"] == 1
    assert "whole_result" not in data
    assert data["final_project_checks"]["confirmed_criteria"] == []
    assert run_final(driver)["outcome"] == "passed"
    data = projection(driver.state)
    assert data["final_project_checks"]["confirmed_criteria"] == ["AC-one"]
    assert compact(driver.state)["final_project_checks"] == data["final_project_checks"]
    render(driver.directory)
    assert "Final project checks" in artifacts.read_text(driver.directory / "dashboard.html")
    assert "Final project checks" in artifacts.read_text(driver.directory / "summary.md")


@pytest.mark.parametrize("procedure", [False, True], ids=["command", "completed-procedure"])
def test_lost_verifier_completed_proof_requires_successor_execution(prepared_project, procedure):
    driver = prepared_project(procedure=procedure)
    if procedure:
        begin(driver)
        previous_procedure = finish(driver)
    assert run_final(driver)["outcome"] == "passed"
    history = deepcopy(driver.state["final_checks"]["evidence"])
    logs = {item["log"]: artifacts.read_bytes(driver.directory / item["log"]) for item in history}
    assert driver.state["final_checks"]["procedures"] == {}
    live = [role["context_id"] for role in driver.state["roles"].values()
            if role["status"] == "active" and role["role_id"] != "project-final"]
    driver.send("resume", {"host_trace": "synthetic-unit-test loss after completed proof", "live_contexts": live}, task_id=None)
    final_role(driver, "successor", successor_of="project-final")
    driver.send("resume", {"host_trace": "synthetic-unit-test successor with no pending work",
        "live_contexts": live + ["successor"], "resolutions": [{"reason": "lost_role", "task_id": None,
        "role_id": "project-final", "successor": "successor", "abandon_procedures": [],
        "evidence": "No unfinished attempt; successor must independently execute the registered checks"}]}, task_id=None)
    assert driver.state["roles"]["project-final"]["status"] == "lost"
    assert driver.state["final_checks"]["evidence"] == history
    assert driver.state["final_checks"]["procedures"] == {}
    _, matches, gaps = evidence(driver.state, driver.directory)
    assert matches == [] and gaps[0]["reason"] == "final_role_lost"
    assert driver.send("finalize", task_id=None)["result"] == "partial"
    driver.send("resume", {"host_trace": "synthetic-unit-test before fresh execution", "live_contexts": live + ["successor"],
        "resolutions": [{"reason": "final_incomplete", "task_id": None,
                         "evidence": "Successor will execute fresh project checks"}]}, task_id=None)
    if procedure:
        from lib.final_checks import basis, procedure_evidence
        state = driver.state
        previous = procedure_evidence(state, state["final_checks"]["checks"][0], driver.directory, basis(state))
        assert previous == {"outcome": "unavailable", "description": "final_role_lost"}
        begin(driver, "successor")
        fresh_procedure = finish(driver, "successor")
        assert fresh_procedure["attempt_id"] != previous_procedure["attempt_id"]
        # A fresh procedure alone cannot reuse the lost predecessor's aggregate.
        assert evidence(driver.state, driver.directory)[1] == []
    result = run_final(driver, "successor")
    assert result["outcome"] == "passed"
    record = log(driver, result)
    assert record["role_id"] == "successor"
    if procedure:
        assert record["outputs"][0]["procedure_attempt"] == fresh_procedure["attempt_id"]
    else:
        assert record["outputs"][0]["command"] == COMMAND
    assert driver.send("finalize", task_id=None)["result"] == "complete"
    assert driver.state["final_checks"]["evidence"][:len(history)] == history
    assert {path: artifacts.read_bytes(driver.directory / path) for path in logs} == logs


@pytest.mark.parametrize("procedure", [False, True], ids=["command", "completed-procedure"])
def test_normally_finished_final_verifier_proof_remains_eligible(prepared_project, procedure):
    driver = prepared_project(procedure=procedure)
    if procedure:
        begin(driver)
        finish(driver)
    assert run_final(driver)["outcome"] == "passed"
    history = deepcopy(driver.state["final_checks"]["evidence"])
    driver.send("role_result", {"role_id": "project-final", "result": "DONE", "trace": "synthetic-unit-test normal completion"}, task_id=None)
    live = [role["context_id"] for role in driver.state["roles"].values() if role["status"] == "active"]
    assert driver.send("resume", {"host_trace": "synthetic-unit-test completed verifier exited", "live_contexts": live}, task_id=None)["status"] == "active"
    assert driver.state["roles"]["project-final"]["status"] == "finished"
    _, matches, gaps = evidence(driver.state, driver.directory)
    assert len(matches) == 1 and gaps == []
    assert driver.send("finalize", task_id=None)["result"] == "complete"
    assert driver.state["final_checks"]["evidence"] == history


def complete_followup(driver):
    """Execute the appended ordinary task with separate synthetic host roles."""
    send = lambda kind, payload=None: driver.send(kind, payload, task_id="TASK-two")
    def role(ident, kind):
        return send("role_register", {"role_id": ident, "kind": kind, "context_id": ident, "fresh": True,
            "host": "codex", "launch_ref": "synthetic-unit-test", "capabilities": {"fresh_context": True}})
    def review(ident):
        role(ident, "reviewer")
        send("review_start", {"role_id": ident})
        send("review_result", {"role_id": ident,
            "verdict": "pass", "findings": [], "test_integrity": "Fixture checks unchanged", "trace": "synthetic-unit-test"})
    project = Path(driver.state["basis"]["project_root"])
    send("worktree_create", {"workspace": str(project.parent / "followup-worktrees")})
    send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    role("followup-author", "executor")
    send("start", {"role_id": "followup-author", "paths": ["followup.txt"]})
    send("check_run", {"role_id": "followup-author", "stage": "baseline"})
    root = Path(driver.state["tasks"]["TASK-two"]["worktree"]["path"])
    (root / "followup.txt").write_text("Approved follow-up\n")
    send("role_result", {"role_id": "followup-author", "result": "DONE", "trace": "synthetic-unit-test"})
    send("candidate")
    role("followup-verifier", "verifier")
    assert send("check_run", {"role_id": "followup-verifier", "stage": "independent"})["outcome"] == "passed"
    review("followup-reviewer")
    send("transfer")
    send("integrate")
    send("candidate")
    role("followup-integration", "verifier")
    assert send("check_run", {"role_id": "followup-integration", "stage": "integration"})["outcome"] == "passed"
    review("followup-integration-reviewer")
    send("commit")
    assert send("accept")["status"] == "accepted"
    role("followup-final", "final_verifier")
    assert send("check_run", {"role_id": "followup-final", "stage": "final"})["outcome"] == "passed"


def test_revised_plan_retains_mandatory_project_checks_after_new_task_finals(prepared_project):
    from test_plan_revision import revise, revised
    driver = prepared_project(memory_worktree=False)
    assert run_final(driver)["outcome"] == "passed"
    original = deepcopy(driver.state["final_checks"])
    for role in driver.state["roles"].values():
        if role["status"] == "active":
            driver.send("role_result", {"role_id": role["role_id"], "result": "DONE", "trace": "synthetic-unit-test"}, task_id=role["task_id"])
    root = Path(driver.state["basis"]["project_root"])
    revise(root, ["one", "two"], lambda tasks: tasks[1].update(depends_on=["TASK-one"]))
    revised(driver)
    assert driver.state["final_checks"]["checks"] == original["checks"]
    assert driver.state["final_checks"]["evidence"] == original["evidence"]
    complete_followup(driver)
    driver.role("new-task-final", "final_verifier")
    assert driver.send("check_run", {"role_id": "new-task-final", "stage": "final"})["outcome"] == "passed"
    assert evidence(driver.state, driver.directory)[2][0]["reason"] == "final_evidence_missing"
    assert driver.send("finalize", task_id=None)["result"] == "partial"
    live = [role["context_id"] for role in driver.state["roles"].values() if role["status"] == "active"]
    driver.send("resume", {"host_trace": "synthetic-unit-test", "live_contexts": live,
        "resolutions": [{"reason": "final_incomplete", "task_id": None, "evidence": "Execute retained project registry at current basis"}]}, task_id=None)
    final_role(driver, "new-project-final")
    assert run_final(driver, "new-project-final")["outcome"] == "passed"
    assert driver.send("finalize", task_id=None)["result"] == "complete"
