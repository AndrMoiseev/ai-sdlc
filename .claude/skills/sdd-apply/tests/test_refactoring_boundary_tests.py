"""Real registry/review operations; synthetic role launches are not behavior evals."""
from copy import deepcopy
import json

import pytest

from lib import artifact_storage as artifacts
from lib.check_registry import selected
from lib.common import Rejected
from lib.roles import refactoring_context
from lib.state_storage import storage
from refactoring_fixtures import BoundaryDriver, boundary_basis


def accept(driver):
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    driver.review()
    driver.integrate(prefix=driver.task_id + "-")
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"


def boundary_candidate(project, split=False):
    driver = BoundaryDriver(boundary_basis(project, split))
    assert driver.start()["outcome"] == "baseline_recorded"
    driver.implement()
    accept(driver)
    driver.task_id = "TASK-two"
    assert driver.start()["outcome"] == "baseline_recorded"
    driver.implement_boundary(split)
    return driver


@pytest.fixture(scope="session")
def boundary_checkpoints(project_template, repository_seeds, tmp_path_factory):
    from unittest.mock import patch
    from checkpoints import LazyCheckpoints
    from conftest import copy_project
    from memory_repository import MemoryRepositories
    from shared_commands import spec_call
    workspace = tmp_path_factory.mktemp("boundary-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)
    def steps():
        with patch("lib.inputs.spec_call", spec_call):
            yield "implemented", boundary_candidate(root)
    return LazyCheckpoints(workspace, backend, steps())


@pytest.fixture
def boundary_checkpoint(boundary_checkpoints, repository_backend, state_backend):
    return boundary_checkpoints["implemented"].restore(repository_backend, state_backend)


@pytest.mark.parametrize("split", [False, True], ids=["merge", "split"])
def test_boundary_evolution_retires_structure_preserves_mixed_test_and_confirms_registry(project, split):
    driver = boundary_candidate(project, split)
    baseline = deepcopy(driver.task["baseline_checks"])
    old_history = deepcopy(driver.state["tasks"]["TASK-one"]["check_registry"]["history"])
    request = driver.revision()
    assert driver.send("checks_revise", request)["status"] == "pending_confirmation"
    context = refactoring_context(driver.state, driver.task)
    evolution = context["test_evolution"]
    assert evolution["transition"]["mapping"] == request["mapping"]
    assert evolution["transition"]["basis"] == request["basis"]
    assert evolution["confirmed_revision"] == 0
    assert {item["id"] for item in context["design"]} >= {"DEC-local-boundary", "AC-preserved"}
    assert any(check["location"] == "check_api.py" and check["criteria"] == ["AC-preserved"] for check in evolution["checks"])
    evolution["transition"]["mapping"].clear()
    assert driver.task["check_registry"]["transition"]["mapping"] == request["mapping"]

    accept(driver)

    checks = selected(driver.state, driver.task, final=True)
    assert "TASK-one/local-result" not in {check["id"] for check in checks}
    assert "AC-preserved" in {criterion for check in checks for criterion in check["criteria"]}
    assert driver.state["tasks"]["TASK-one"]["check_registry"]["history"] == old_history
    assert driver.task["baseline_checks"] == baseline
    assert driver.state["acceptance"]["AC-local"]["lifetime"] == "persistent"
    assert driver.task["check_registry"]["confirmed_revision"] == driver.task["check_registry"]["revision"]
    if split:
        assert any(check["location"] == "check_contract.py" for check in checks)


@pytest.mark.parametrize("damage,code", [("mapping", "revision_mapping"), ("preservation", "criteria_uncovered"),
                                        ("authorization", "revision_basis")])
def test_boundary_revision_cannot_drop_mapping_authorization_or_mixed_guarantee(boundary_checkpoint, damage, code):
    driver = boundary_checkpoint
    request = driver.revision()
    if damage == "mapping":
        request["mapping"].pop("TASK-one/local-result")
    elif damage == "authorization":
        request["basis"]["test_changes"] = ["unapproved-retirement"]
    else:
        request["after"] = [check for check in request["after"] if "AC-preserved" not in check["criteria"]]
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send("checks_revise", request)
    assert error.value.code == code
    assert storage(driver.directory).read() == before


def test_moved_atomicity_check_rejects_real_regression(boundary_checkpoint):
    driver = boundary_checkpoint
    driver.send("checks_revise", driver.revision())
    (driver.root / "ledger.py").write_text(
        "def transfer(accounts, amount):\n    accounts['left'] -= amount\n"
        "    if amount < 0 or amount > accounts['left'] + amount:\n        raise ValueError('invalid amount')\n"
        "    accounts['right'] += amount\n", encoding="utf-8")
    driver.freeze()
    result = driver.verify()
    assert result["outcome"] == "failed"
    log = json.loads(artifacts.read_text(driver.directory / result["log"]))
    assert any(output["outcome"] == "failed" and "AC-preserved" in output["criteria"] for output in log["outputs"])
    assert driver.task["check_registry"]["confirmed_revision"] == 0
