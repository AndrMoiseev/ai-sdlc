"""Real local acceptance gates for refactoring; synthetic role attestations only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from lib.candidates import resolve
from lib.common import Rejected, digest, write_json
from refactoring_fixtures import AcceptanceDriver, approved_basis


def driver_for(project, tmp_path, parallel, work_kind="refactoring"):
    driver = AcceptanceDriver(approved_basis(project, work_kind), parallel=parallel)
    if parallel:
        driver.send("worktree_create", {"workspace": str(tmp_path / "task-worktrees")})
    return driver


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize("work_kind", ["change", "refactoring"])
def test_refactoring_acceptance_real_pipeline_preserves_local_contract(project, tmp_path, parallel, work_kind):
    driver = driver_for(project, tmp_path, parallel, work_kind)
    assert driver.start()["outcome"] == "baseline_recorded"
    baseline = deepcopy(driver.task["baseline_checks"])
    driver.implement()
    driver.freeze()
    reference = driver.task["candidate"]
    assert (driver.directory / reference["path"]).is_file()
    if work_kind == "refactoring":
        assert not (project / "sdd/changes/demo/execution/candidates").exists()
    assert driver.verify()["outcome"] == "passed"
    assert driver.review()["status"] == ("integrating" if parallel else "committing")
    if parallel:
        assert driver.integrate_verified()["outcome"] == "passed"
        with pytest.raises(Rejected) as error:
            driver.send("commit")
        assert error.value.code == "commit_phase"
        assert driver.review("integration-reviewer")["status"] == "committing"
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"
    assert driver.task["baseline_checks"] == baseline
    if work_kind == "refactoring":
        assert "covers" not in driver.task["plan"]
        assert [check["id"] for check in driver.task["checks"]] == ["TASK-one/local-result", "TASK-one/api-regression"]
        assert baseline["outputs"][0]["outcome"] == "planned_absence"
        assert baseline["outputs"][1]["outcome"] == "passed"
        assert baseline["registered_checks"][0]["setup"] is None
        assert driver.task["check_registry"]["revision"] == 2
        assert driver.state["final"] is None
        assert driver.state["verification"]["CHECK-whole"]["criteria"] == ["AC-result", "AC-preserved"]


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_packets_have_real_local_and_architectural_context(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    driver.implement()
    driver.freeze()
    packet = json.loads(Path(driver.role("verifier", "verifier")["packet"]).read_text(encoding="utf-8"))
    context = packet["refactoring"]
    assert context["scope"] == driver.task["plan"]["scope"]
    assert [record["id"] for record in context["acceptance"]] == ["AC-local"]
    assert context["preserves"] == ["AC-preserved"]
    assert context["contributes_to"] == ["AC-result"]
    assert context["test_changes"][0]["id"] == "add-local-check"
    assert {record["id"] for record in context["design"]} == {"AC-result", "AC-preserved", "DEC-local-boundary"}
    assert context["check_registry"]["revision"] == driver.task["check_registry"]["revision"]
    assert context["check_registry"]["history"][0]["checks_hash"] == digest(driver.task["check_registry"]["history"][0]["checks"])
    assert context["baseline"]["registry_revision"] == 1
    assert context["baseline"]["outputs"][1]["outcome"] == "passed"
    assert (driver.directory / context["baseline"]["log"]).is_file()
    assert all(Path(path).is_file() for path in context["sources"].values())
    assert "contributes_to" in context["whole_result"]


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize("damage", ["omit", "unrelated-success", "criteria"])
def test_refactoring_acceptance_unapproved_registry_edit_cannot_freeze(project, tmp_path, parallel, damage):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    driver.implement()
    def corrupt(task):
        if damage == "omit":
            task["checks"].pop()
        elif damage == "unrelated-success":
            task["checks"][1]["run"] = {"command": [sys.executable, "-B", "-c", "raise SystemExit(0)"]}
        else:
            task["checks"][1]["criteria"] = ["AC-result"]
    driver.corrupt(corrupt)
    before = (driver.directory / "state.json").read_bytes()
    driver.send("role_result", {"role_id": "author", "result": "DONE", "trace": "synthetic-unit-test"})
    after_author = (driver.directory / "state.json").read_bytes()
    with pytest.raises(Rejected) as error:
        driver.send("candidate")
    assert error.value.code == "registry_changed"
    assert (driver.directory / "state.json").read_bytes() == after_author
    assert before != after_author
    assert driver.task["status"] == "running"


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_unavailable_new_check_does_not_accept(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    (driver.root / "result.txt").write_text("local implemented\n")
    (driver.root / "check_local.py").write_text("assert True\n")
    driver.send("check_setup", {"check_id": "TASK-one/local-result", "command": [str(driver.root / "missing-runner")],
                               "description": "New local boundary confirmation requires this runner"})
    driver.freeze()
    driver.role("reviewer", "reviewer")
    result = driver.verify()
    assert result["outcome"] == "unavailable"
    output = driver.log(result)["outputs"][0]
    assert output["outcome"] == "unavailable" and output["exit_code"] is None
    assert driver.task["status"] != "accepted"
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "reviewer"})
    assert error.value.code == "run_blocked"
    with pytest.raises(Rejected) as error:
        driver.send("accept")
    assert error.value.code == "run_blocked"


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_stale_source_blocks_review_and_accept(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    driver.implement()
    driver.freeze()
    driver.verify()
    driver.role("reviewer", "reviewer")
    (driver.root / "result.txt").write_text("changed after verification\n")
    before = (driver.directory / "state.json").read_bytes()
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "reviewer"})
    assert error.value.code == "stale_candidate"
    with pytest.raises(Rejected) as error:
        driver.send("accept")
    assert error.value.code == "commit_phase"
    assert (driver.directory / "state.json").read_bytes() == before


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_registry_extension_requires_new_checks_and_review(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    driver.implement()
    driver.freeze()
    driver.verify()
    old_candidate = driver.task["candidate"]
    old_logs = {item["log"]: (driver.directory / item["log"]).read_bytes() for item in driver.task["evidence"]}
    driver.review(verdict="more_checks")
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [
        {"id": "review-local", "source": "review", "criteria": ["AC-local", "AC-preserved"],
         "run": {"command": [sys.executable, "-B", "check.py"]}}]})
    assert resolve(driver.state, old_candidate)["checks"] != resolve(driver.state, driver.task["candidate"])["checks"]
    driver.role("next-reviewer", "reviewer")
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "next-reviewer"})
    assert error.value.code == "required_checks"
    assert driver.verify()["outcome"] == "passed"
    driver.send("review_start", {"role_id": "next-reviewer"})
    with pytest.raises(Rejected) as error:
        driver.send("review_result", {"role_id": "next-reviewer", "candidate": old_candidate, "verdict": "pass",
                                      "findings": [], "test_integrity": "Inspected", "trace": "synthetic-unit-test"})
    assert error.value.code == "stale_review"
    assert driver.task["review_rounds_started"] == 2
    assert driver.task["check_registry"]["revision"] == 3
    assert all((driver.directory / name).read_bytes() == content for name, content in old_logs.items())


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_real_failure_requires_reserved_repair_and_retains_history(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    baseline = deepcopy(driver.task["baseline_checks"])
    driver.implement()
    (driver.root / "check.py").write_text("raise SystemExit(7)\n")
    driver.freeze()
    failed = driver.verify()
    assert failed["outcome"] == "failed"
    assert driver.log(failed)["outputs"][1]["exit_code"] == 7
    failed_bytes = (driver.directory / failed["log"]).read_bytes()
    with pytest.raises(Rejected) as error:
        driver.verify()
    assert error.value.code == "repair_cycle_required"
    driver.send("repair", {"reason": "Restore preserved API regression"})
    assert driver.task["test_repair_cycles_started"] == 1
    (driver.root / "check.py").write_text("assert 2 + 3 == 5\n")
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    driver.review()
    if parallel:
        assert driver.integrate_verified()["outcome"] == "passed"
        driver.review("integration-reviewer")
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"
    assert driver.task["test_repair_cycles_started"] == 1
    assert driver.task["review_rounds_started"] == (2 if parallel else 1)
    assert driver.task["baseline_checks"] == baseline
    assert (driver.directory / failed["log"]).read_bytes() == failed_bytes
    assert any(item["outcome"] == "failed" for item in driver.task["evidence"])


@pytest.mark.parametrize("parallel", [False, True])
def test_refactoring_acceptance_contribution_cannot_be_registered_as_local_proof(project, tmp_path, parallel):
    driver = driver_for(project, tmp_path, parallel)
    before = (driver.directory / "state.json").read_bytes()
    with pytest.raises(Rejected) as error:
        driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [
            {"id": "whole-as-local", "source": "executor", "criteria": ["AC-result"],
             "run": {"command": [sys.executable, "-B", "check.py"]}}]})
    assert error.value.code == "check_schema"
    assert (driver.directory / "state.json").read_bytes() == before


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize("damage", ["command", "revision", "foreign-task"])
def test_refactoring_acceptance_rejects_evidence_for_unrelated_command_or_basis(project, tmp_path, parallel, damage):
    driver = driver_for(project, tmp_path, parallel)
    driver.start()
    driver.implement()
    driver.freeze()
    result = driver.verify()
    driver.role("reviewer", "reviewer")
    log = driver.log(result)
    if damage == "command":
        log["outputs"][0]["command"] = [sys.executable, "-B", "-c", "raise SystemExit(0)"]
    elif damage == "revision":
        log["registry_revision"] -= 1
    else:
        log["task_id"] = "TASK-another"
    path = driver.directory / result["log"]
    write_json(path, log)
    def replace_hash(task):
        for item in task["evidence"]:
            if item["log"] == result["log"]:
                item["log_hash"] = digest(path.read_bytes())
    driver.corrupt(replace_hash)
    before = (driver.directory / "state.json").read_bytes()
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "reviewer"})
    assert error.value.code == ("evidence_command" if damage == "command" else "evidence_basis")
    assert (driver.directory / "state.json").read_bytes() == before
