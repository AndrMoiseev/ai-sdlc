"""Real local acceptance gates for refactoring; synthetic role attestations only."""
from lib import artifact_storage as artifacts
from lib.state_storage import storage
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from lib.common import Rejected, digest, write_json
from refactoring_fixtures import AcceptanceDriver, approved_basis


@pytest.fixture(scope="session")
def acceptance_templates(project_template, tmp_path_factory, repository_seeds):
    """Validate immutable inputs once, then seed independent test repositories."""
    templates = {}
    from unittest.mock import patch
    from shared_commands import spec_call
    from conftest import copy_project
    from lib.repository import use_repositories
    from memory_repository import MemoryRepositories, capture_seed
    for kind in ("change", "refactoring"):
        backend = MemoryRepositories(repository_seeds)
        root = copy_project(project_template, tmp_path_factory.mktemp(kind) / "project", backend,
                            omit=("sdd",) if kind == "refactoring" else ())
        with use_repositories(backend), patch("lib.inputs.spec_call", spec_call):
            templates[kind] = (root, approved_basis(root, kind))
        seed = capture_seed(root, backend(root))
        repository_seeds[seed["head"]] = seed
        repository_seeds[root] = seed
    return templates


@pytest.fixture
def work_kind():
    return "refactoring"


@pytest.fixture
def project(tmp_path, acceptance_templates, work_kind, repository_backend, working_copies):
    from conftest import copy_project
    from memory_repository import MemoryRepositories
    root, _ = acceptance_templates[work_kind]
    if isinstance(repository_backend, MemoryRepositories):
        return working_copies.copy(root, repository_backend)
    return copy_project(root, tmp_path / "project", repository_backend)


@pytest.fixture
def basis(project, acceptance_templates, work_kind):
    _, template = acceptance_templates[work_kind]
    result = deepcopy(template)
    directory = "changes" if work_kind == "change" else "refactoring"
    result.update(project_root=str(project), change_root=str(project / "sdd" / directory / "demo"))
    return result


@pytest.mark.parametrize("work_kind", ["change", "refactoring"])
def test_acceptance_template_matches_validation_and_is_isolated(project, basis, acceptance_templates, work_kind):
    from lib.inputs import validate
    from lib.repository import repository
    assert basis == validate(project, "demo", basis["instruction"],
                             work_kind=work_kind)
    root, template = acceptance_templates[work_kind]
    original = (root / "check.py").read_bytes()
    (project / "check.py").write_text("raise SystemExit(1)\n")
    basis["tasks"][0]["status"] = "changed"
    assert (root / "check.py").read_bytes() == original
    assert template["tasks"][0]["status"] == "pending"
    assert not repository(root).dirty()


def driver_for(basis, tmp_path):
    driver = AcceptanceDriver(basis)
    driver.send("worktree_create", {"workspace": str(tmp_path / "task-worktrees")})
    return driver


@pytest.fixture(scope="session")
def acceptance_checkpoints(acceptance_templates, repository_seeds, tmp_path_factory):
    from conftest import copy_project
    from checkpoints import LazyCheckpoints
    from memory_repository import MemoryRepositories
    template_root, template_basis = acceptance_templates["refactoring"]
    workspace = tmp_path_factory.mktemp("acceptance-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(template_root, workspace / "project", backend)
    basis = deepcopy(template_basis)
    basis.update(project_root=str(root), change_root=str(root / "sdd/refactoring/demo"))
    def steps():
        driver = driver_for(basis, workspace)
        yield "pending", driver
        assert driver.start()["outcome"] == "baseline_recorded"
        yield "started", driver
        driver.implement()
        yield "implemented", driver
        driver.freeze()
        yield "frozen", driver
        assert driver.verify()["outcome"] == "passed"
        yield "verified", driver
    return LazyCheckpoints(workspace, backend, steps())


@pytest.fixture
def acceptance_checkpoint(acceptance_checkpoints, repository_backend, state_backend):
    return lambda stage: acceptance_checkpoints[stage].restore(repository_backend, state_backend)


@pytest.mark.parametrize("work_kind", ["change", "refactoring"])
def test_refactoring_acceptance_real_pipeline_preserves_local_contract(project, basis, tmp_path, work_kind):
    driver = driver_for(basis, tmp_path)
    assert driver.start()["outcome"] == "baseline_recorded"
    baseline = deepcopy(driver.task["baseline_checks"])
    driver.implement()
    driver.freeze()
    assert "candidate" not in driver.task
    assert not artifacts.paths(driver.directory / "candidates", "*.json")
    if work_kind == "refactoring":
        assert not (project / "sdd/changes/demo/execution/candidates").exists()
    assert driver.verify()["outcome"] == "passed"
    assert driver.review()["status"] == "integrating"
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


def test_refactoring_acceptance_packets_have_real_local_and_architectural_context(acceptance_checkpoint):
    driver = acceptance_checkpoint("frozen")
    packet = json.loads(artifacts.read_text(driver.role("verifier", "verifier")["packet"]))
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
    assert artifacts.exists(driver.directory / context["baseline"]["log"])
    assert all(Path(path).is_file() for path in context["sources"].values())
    assert "contributes_to" in context["whole_result"]


@pytest.mark.parametrize("damage", ["omit", "unrelated-success", "criteria"])
def test_refactoring_acceptance_unapproved_registry_edit_cannot_freeze(acceptance_checkpoint, damage):
    driver = acceptance_checkpoint("implemented")
    def corrupt(task):
        if damage == "omit":
            task["checks"].pop()
        elif damage == "unrelated-success":
            task["checks"][1]["run"] = {"command": [sys.executable, "-B", "-c", "raise SystemExit(0)"]}
        else:
            task["checks"][1]["criteria"] = ["AC-result"]
    driver.corrupt(corrupt)
    before = storage(driver.directory).read()
    driver.send("role_result", {"role_id": "author", "result": "DONE", "trace": "synthetic-unit-test"})
    after_author = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("candidate")
    assert error.value.code == "registry_changed"
    assert storage(driver.directory).read() == after_author
    assert before != after_author
    assert driver.task["status"] == "running"


@pytest.mark.native_process
def test_refactoring_acceptance_unavailable_new_check_does_not_accept(acceptance_checkpoint):
    driver = acceptance_checkpoint("started")
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


def test_refactoring_acceptance_stale_source_blocks_review_and_accept(acceptance_checkpoint):
    driver = acceptance_checkpoint("verified")
    driver.role("reviewer", "reviewer")
    (driver.root / "result.txt").write_text("changed after verification\n")
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "reviewer"})
    assert error.value.code == "dirty_candidate"
    with pytest.raises(Rejected) as error:
        driver.send("accept")
    assert error.value.code == "commit_phase"
    assert storage(driver.directory).read() == before


def test_refactoring_acceptance_registry_extension_requires_new_checks_and_review(acceptance_checkpoint):
    driver = acceptance_checkpoint("verified")
    old_logs = {item["log"]: artifacts.read_bytes(driver.directory / item["log"]) for item in driver.task["evidence"]}
    driver.review(verdict="more_checks")
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [
        {"id": "review-local", "source": "review", "criteria": ["AC-local", "AC-preserved"],
         "run": {"command": [sys.executable, "-B", "check.py"]}}]})
    driver.role("next-reviewer", "reviewer")
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "next-reviewer"})
    assert error.value.code == "evidence_basis"
    assert driver.verify()["outcome"] == "passed"
    driver.send("review_start", {"role_id": "next-reviewer"})
    with pytest.raises(Rejected) as error:
        driver.send("review_result", {"role_id": "next-reviewer", "candidate": {"path": "retired-reference"}, "verdict": "pass",
                                      "findings": [], "test_integrity": "Inspected", "trace": "synthetic-unit-test"})
    assert error.value.code == "review_schema"
    assert driver.task["review_rounds_started"] == 2
    assert driver.task["check_registry"]["revision"] == 3
    assert all(artifacts.read_bytes(driver.directory / name) == content for name, content in old_logs.items())


def test_refactoring_acceptance_real_failure_requires_reserved_repair_and_retains_history(acceptance_checkpoint):
    driver = acceptance_checkpoint("implemented")
    baseline = deepcopy(driver.task["baseline_checks"])
    (driver.root / "check.py").write_text("raise SystemExit(7)\n")
    driver.freeze()
    failed = driver.verify()
    assert failed["outcome"] == "failed"
    assert driver.log(failed)["outputs"][1]["exit_code"] == 7
    failed_bytes = artifacts.read_bytes(driver.directory / failed["log"])
    with pytest.raises(Rejected) as error:
        driver.verify()
    assert error.value.code == "repair_cycle_required"
    driver.send("repair", {"reason": "Restore preserved API regression"})
    assert driver.task["test_repair_cycles_started"] == 1
    (driver.root / "check.py").write_text("assert 2 + 3 == 5\n")
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    driver.review()
    assert driver.integrate_verified()["outcome"] == "passed"
    driver.review("integration-reviewer")
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"
    assert driver.task["test_repair_cycles_started"] == 1
    assert driver.task["review_rounds_started"] == 2
    assert driver.task["baseline_checks"] == baseline
    assert artifacts.read_bytes(driver.directory / failed["log"]) == failed_bytes
    assert any(item["outcome"] == "failed" for item in driver.task["evidence"])


def test_refactoring_acceptance_contribution_cannot_be_registered_as_local_proof(acceptance_checkpoint):
    driver = acceptance_checkpoint("pending")
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [
            {"id": "whole-as-local", "source": "executor", "criteria": ["AC-result"],
             "run": {"command": [sys.executable, "-B", "check.py"]}}]})
    assert error.value.code == "check_schema"
    assert storage(driver.directory).read() == before


@pytest.mark.parametrize("damage", ["command", "revision", "foreign-task"])
def test_refactoring_acceptance_rejects_evidence_for_unrelated_command_or_basis(acceptance_checkpoint, damage):
    driver = acceptance_checkpoint("verified")
    result = driver.task["evidence"][-1]
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
                item["log_hash"] = digest(artifacts.read_bytes(path))
    driver.corrupt(replace_hash)
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("review_start", {"role_id": "reviewer"})
    assert error.value.code == ("evidence_command" if damage == "command" else "evidence_basis")
    assert storage(driver.directory).read() == before
