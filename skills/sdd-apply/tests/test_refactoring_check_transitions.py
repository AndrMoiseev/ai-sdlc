"""Approved check evolution through the engine with isolated test adapters."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from lib.check_registry import selected
from lib.common import Rejected
from lib.repository import repository
from lib.state import apply
from lib.state_storage import storage
from lib import artifact_storage as artifacts
from lib.state_history import lookup
from lib.verification import current, valid_evidence
from refactoring_fixtures import AcceptanceDriver, RegistryDriver, approved_basis, transition_basis


def start(driver, task_id, tmp_path):
    driver.task_id = task_id
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    assert driver.start()["outcome"] == "baseline_recorded"


def finish(driver):
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    driver.review()
    driver.integrate(prefix=driver.task_id + "-")
    driver.send("commit")
    assert "candidate" not in driver.task
    if driver.task_id == "TASK-two":
        source = current(driver.state, driver.task)
        repo = repository(driver.root)
        assert source["commit"] == repo.head() == driver.task["commits"][-1]["sha"]
        assert source["dirty_paths"] == []
        tracked = repo.tracked(source["commit"])
        for path in ("adapter.py", "check.py"):
            assert path not in tracked
            assert not (driver.root / path).exists()
    assert driver.send("accept")["status"] == "accepted"


def removing(project, tmp_path, non_topological=False):
    def permute_numbers(documents):
        numbers = {"TASK-one": 2, "TASK-two": 1, "TASK-three": 3}
        for record in documents["tasks"]:
            if record["sdd_record"] == "task":
                record["number"] = numbers[record["id"]]
    driver = RegistryDriver(transition_basis(project, revise_documents=permute_numbers if non_topological else None))
    start(driver, "TASK-one", tmp_path)
    driver.implement()
    finish(driver)
    start(driver, "TASK-two", tmp_path)
    driver.implement()
    return driver


@pytest.fixture(scope="session")
def removal_checkpoints(project_template, repository_seeds, tmp_path_factory):
    from conftest import copy_project
    from checkpoints import LazyCheckpoints
    from memory_repository import MemoryRepositories
    workspace = tmp_path_factory.mktemp("removal-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)

    def steps():
        driver = removing(root, workspace)
        yield "implemented", driver
        driver.send("checks_revise", driver.revision())
        driver.freeze()
        yield "frozen", driver
        assert driver.verify()["outcome"] == "passed"
        driver.review()
        driver.integrate(prefix=driver.task_id + "-")
        driver.send("commit")
        yield "committed", driver

    return LazyCheckpoints(workspace, backend, steps())


@pytest.fixture
def removal_checkpoint(removal_checkpoints, repository_backend, state_backend):
    return lambda stage="implemented", **options: removal_checkpoints[stage].restore(repository_backend, state_backend, **options)


def event(driver, kind, payload, ident):
    state = driver.state
    return dict(event_id=ident, run_id=state["run_id"], expected_revision=state["revision"],
                type=kind, task_id=driver.task_id, payload=payload)


def assert_rejected(driver, code, kind, payload):
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send(kind, payload)
    assert error.value.code == code
    assert storage(driver.directory).read() == before


def project_check(ident, criterion, filename="check.py"):
    return dict(id=ident, criteria=[criterion], source="project-rule", location=filename,
                run={"command": [sys.executable, "-B", filename]})


@pytest.fixture(scope="session")
def collision_checkpoints(project_template, repository_seeds, tmp_path_factory):
    from conftest import copy_project
    from checkpoints import LazyCheckpoints
    from memory_repository import MemoryRepositories
    workspace = tmp_path_factory.mktemp("collision-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)

    def steps():
        driver = RegistryDriver(transition_basis(root))
        assert driver.start(additional=[project_check("shared-check", "AC-preserved")])["outcome"] == "baseline_recorded"
        driver.implement()
        finish(driver)
        driver.task_id = "TASK-two"
        yield "checks_register", driver
        assert driver.start()["outcome"] == "baseline_recorded"
        driver.implement()
        driver.send("checks_revise", driver.revision())
        driver.freeze()
        assert driver.verify()["outcome"] == "passed"
        driver.review(verdict="more_checks")
        yield "checks_extend", driver

    return LazyCheckpoints(workspace, backend, steps())


@pytest.mark.parametrize("operation", ["checks_register", "checks_extend"])
@pytest.mark.parametrize("ident", ["shared-check", "TASK-one/api-regression"])
def test_cross_task_check_collision_cannot_replace_confirmed_obligation(
        collision_checkpoints, repository_backend, state_backend, operation, ident):
    driver = collision_checkpoints[operation].restore(repository_backend, state_backend, memory_worktree=True)
    old = deepcopy(selected(driver.state, driver.state["tasks"]["TASK-one"], final=True))
    collision = project_check(ident, "AC-removed", "check_removed.py")
    payload = {"additional": [collision]}
    if operation == "checks_register":
        payload["inventory"] = {"instructions": [], "ci": []}
    else:
        payload["review_round"] = driver.task["reviews"][-1]["round_id"]
    before = deepcopy(selected(driver.state, driver.task, final=operation == "checks_register"))
    assert_rejected(driver, "duplicate_check", operation, payload)
    assert selected(driver.state, driver.task, final=operation == "checks_register") == before
    assert selected(driver.state, driver.task, final=True) == old
    retained = next(check for check in before if check["id"] == ident)
    assert retained["criteria"] == ["AC-preserved"]
    assert retained["run"]["command"] == [sys.executable, "-B", "check_api.py" if operation == "checks_extend" else "check.py"]


def test_additional_check_cannot_preempt_a_future_generated_id(project):
    driver = RegistryDriver(transition_basis(project))
    assert_rejected(driver, "duplicate_check", "checks_register", {
        "inventory": {"instructions": [], "ci": []},
        "additional": [project_check("TASK-two/local-result", "AC-preserved")]})
    assert driver.task["checks"] == []


def test_ordinary_check_ids_remain_task_local(project):
    basis = approved_basis(project, "change")
    second = deepcopy(basis["tasks"][0])
    second.update(id="TASK-two", number=2, depends_on=["TASK-one"])
    basis["tasks"].append(second)
    driver = AcceptanceDriver(basis)
    for ident in ("TASK-one", "TASK-two"):
        result = driver.send("checks_register", {"inventory": {"instructions": [], "ci": []},
            "additional": [project_check("shared-check", "AC-one")]}, task_id=ident)
        assert [check["id"] for check in result["checks"]] == ["plan-1", "shared-check"]


def test_refactoring_check_transitions_confirm_after_accept_and_apply_to_later_tasks(project, tmp_path):
    # Exercise the full lifecycle with numbering that disagrees with dependencies.
    # Ordering combinations belong to scheduler/wave tests, not repeated migrations.
    driver = removing(project, tmp_path, non_topological=True)
    assert [driver.state["tasks"][ident]["plan"]["number"] for ident in ("TASK-one", "TASK-two", "TASK-three")] == [2, 1, 3]
    old = deepcopy(driver.state["tasks"]["TASK-one"])
    logs = {item["log"]: artifacts.read_bytes(driver.directory / item["log"])
            for item in old["evidence"]}
    baseline = deepcopy(driver.task["baseline_checks"])
    assert any(item["check_id"] == "TASK-one/local-result" and item["outcome"] == "passed" for item in baseline["outputs"])
    request = driver.revision()
    result = driver.send("checks_revise", request)
    assert result["status"] == "pending_confirmation"
    assert result["registry_revision"] == request["registry_revision"] + 1
    recovered = driver.resume()["check_registries"]
    assert recovered["TASK-one"]["confirmed_revision"] == old["check_registry"]["revision"]
    assert recovered["TASK-two"]["confirmed_revision"] == 0
    assert recovered["TASK-two"]["pending_transition"]["before"] == request["before"]
    assert any(item["id"] == "TASK-one/local-result" for item in selected(driver.state, driver.task, final=True))
    assert all(item["id"] != "TASK-one/local-result" for item in selected(driver.state, driver.task))
    finish(driver)
    assert driver.task["check_registry"]["confirmed_revision"] == result["registry_revision"]
    confirmed = selected(driver.state, driver.task, final=True)
    assert "TASK-one/local-result" not in {check["id"] for check in confirmed}
    assert {(check["setup"] or check["run"])["command"][-1] for check in confirmed} == {"check_api.py", "check_removed.py"}
    assert driver.resume()["check_registries"]["TASK-two"]["pending_transition"] is None
    assert driver.task["baseline_checks"] == baseline
    assert driver.state["tasks"]["TASK-one"]["evidence"] == old["evidence"]
    assert all(artifacts.read_bytes(driver.directory / name) == content for name, content in logs.items())
    start(driver, "TASK-three", tmp_path)
    later_baseline = driver.task["baseline_checks"]
    assert "TASK-one/local-result" not in {item["check_id"] for item in later_baseline["outputs"]}
    assert {item["command"][-1] for item in later_baseline["outputs"] if "command" in item} == {"check_api.py", "check_removed.py"}
    api_baseline = [item for item in later_baseline["outputs"] if item.get("criteria") == ["AC-preserved"]]
    assert {item["check_id"] for item in api_baseline} == {"TASK-one/api-regression", "TASK-two/api-regression"}
    assert {tuple(item["command"]) for item in api_baseline} == {(sys.executable, "-B", "check_api.py")}
    driver.implement()
    finish(driver)
    result = driver.send("finalize", task_id=None)
    assert result["result"] == "complete"
    whole = {c for check in driver.state["verification"].values() for c in check["criteria"]}
    assert result["unassessed_criteria"] == sorted(whole - set(result["accepted_criteria"]))
    assert result["unassessed_criteria"]


@pytest.mark.parametrize("damage,code", [
    ("revision", "registry_revision_conflict"), ("before", "registry_revision_conflict"),
    ("permission", "revision_basis"), ("until-task", "revision_basis"),
    ("mapping", "revision_mapping"), ("preserves", "revision_preservation"),
    ("coverage", "criteria_uncovered"), ("contribution", "check_schema"),
    ("string-command", "command_format"), ("duplicate", "duplicate_check"),
])
def test_refactoring_check_transitions_reject_unapproved_or_incomplete_revision(removal_checkpoint, damage, code):
    driver = removal_checkpoint(memory_worktree=True)
    request = driver.revision()
    if damage == "revision":
        request["registry_revision"] -= 1
    elif damage == "before":
        request["before"] = request["before"][:-1]
    elif damage == "permission":
        request["basis"]["test_changes"] = ["unknown-group"]
    elif damage == "until-task":
        request["basis"]["transitional_criteria"] = ["AC-removed"]
    elif damage == "mapping":
        request["mapping"] = {}
    elif damage == "preserves":
        request["preserves"] = []
    elif damage == "coverage":
        request["after"] = [item for item in request["after"] if "AC-preserved" not in item["criteria"]]
    elif damage == "contribution":
        request["after"][0]["criteria"] = ["AC-result"]
    elif damage == "string-command":
        request["after"][0]["run"]["command"] = "python check_api.py"
    elif damage == "duplicate":
        request["after"].append(deepcopy(request["after"][0]))
    assert_rejected(driver, code, "checks_revise", request)
    assert driver.task["check_registry"]["revision"] == request["registry_revision"] + (1 if damage == "revision" else 0)


@pytest.mark.native_process
def test_refactoring_check_transitions_event_repeat_conflicts_and_new_revision(removal_checkpoint):
    driver = removal_checkpoint()
    result = driver.send("checks_revise", driver.revision())
    original_event = deepcopy(lookup(driver.state.objects, driver.state["event_index"], f"event-{driver.number}")["event"])
    before = storage(driver.directory).read()
    assert apply(driver.directory, original_event) == result
    assert storage(driver.directory).read() == before
    conflict = deepcopy(original_event)
    conflict["payload"]["reason"] = "Different content"
    with pytest.raises(Rejected) as error:
        apply(driver.directory, conflict)
    assert error.value.code == "event_conflict"
    stale = deepcopy(original_event)
    stale["event_id"] = "different-id-stale-revision"
    with pytest.raises(Rejected) as error:
        apply(driver.directory, stale)
    assert error.value.code == "revision_conflict"
    assert storage(driver.directory).read() == before
    driver.freeze()
    checked = driver.verify()
    assert checked["outcome"] == "passed"
    old_log = artifacts.read_bytes(driver.directory / checked["log"])
    driver.send("repair", {"reason": "Change the approved API runner detail", "defect_evidence": "The moved API runner needs explicit UTF-8 mode"})
    revised = driver.revision()
    revised["before"] = deepcopy(selected(driver.state, driver.task))
    revised["after"] = deepcopy(revised["before"])
    for check in revised["after"]:
        if "AC-preserved" in check["criteria"]:
            check["run"]["command"] = [sys.executable, "-B", "-X", "utf8", "check_api.py"]
    revised["basis"] = {"test_changes": ["move-api-check"]}
    revised["mapping"] = {item["id"]: "Keep the same moved API assertion with explicit runner encoding" for item in revised["after"] if item not in revised["before"]}
    next_result = driver.send("checks_revise", revised)
    assert next_result["registry_revision"] == result["registry_revision"] + 1
    driver.freeze()
    driver.role("new-reviewer", "reviewer")
    assert_rejected(driver, "evidence_basis", "review_start", {"role_id": "new-reviewer"})
    assert driver.verify()["outcome"] == "passed"
    assert artifacts.read_bytes(driver.directory / checked["log"]) == old_log
    assert driver.task["test_repair_cycles_started"] == 0


@pytest.mark.native_process
@pytest.mark.parametrize("outcome", ["failed", "unavailable"])
def test_refactoring_check_transitions_failed_replacement_never_confirms(removal_checkpoint, outcome):
    driver = removal_checkpoint()
    request = driver.revision()
    if outcome == "failed":
        (driver.root / "check_removed.py").write_text("raise SystemExit(17)\n", encoding="utf-8")
    else:
        for check in request["after"]:
            if "AC-preserved" in check["criteria"]:
                check["run"]["command"] = [str(driver.root / "missing-runner")]
    driver.send("checks_revise", request)
    driver.freeze()
    driver.role("blocked-reviewer", "reviewer")
    result = driver.verify()
    assert result["outcome"] == outcome
    if outcome == "failed":
        assert next(item for item in driver.log(result)["outputs"] if item["check_id"] == "TASK-two/local-result")["exit_code"] == 17
    assert_rejected(driver, "run_blocked" if outcome == "unavailable" else "required_checks", "review_start", {"role_id": "blocked-reviewer"})
    assert driver.task["status"] != "accepted"
    assert driver.task["check_registry"].get("confirmed_revision", 0) == 0
    assert driver.resume()["check_registries"]["TASK-two"]["pending_transition"] is not None
    if outcome == "failed":
        driver.explorer("retry-explorer", "independent")
        assert_rejected(driver, "repair_cycle_required", "check_run", {"role_id": "retry-explorer", "stage": "independent"})
        driver.send("repair", {"reason": "Restore the approved replacing-state assertion"})
        assert driver.task["test_repair_cycles_started"] == 1
        assert driver.resume()["check_registries"]["TASK-two"]["pending_transition"] is not None
        assert driver.task["active_repair"] == "cycle-1"


@pytest.mark.parametrize("boundary,native", [
    ("log-before", False), ("log-after", False), ("state-before", False),
    # Keep one real orphan file across recovery; storage contracts cover failed replacement.
    pytest.param("log-after", True, marks=pytest.mark.native_state),
])
def test_refactoring_check_transitions_resume_after_interrupted_evidence(removal_checkpoint, monkeypatch, boundary, native):
    from lib import state, verification
    driver = removal_checkpoint("frozen", memory_worktree=not native)
    driver.explorer("interrupted-explorer", "independent")
    attempt = event(driver, "check_run", {"role_id": "interrupted-explorer", "stage": "independent"}, "interrupted-evidence")
    target = type(storage(driver.directory)) if boundary == "state-before" else verification
    method = "save" if boundary == "state-before" else "write_json"
    original_write = getattr(target, method)
    before = storage(driver.directory).read()
    evidence = deepcopy(driver.task["evidence"])
    def interrupt(*args):
        if boundary == "log-after":
            original_write(*args)
        raise OSError("Injected interruption at " + boundary)
    with monkeypatch.context() as patch:
        patch.setattr(target, method, interrupt)
        with pytest.raises(OSError, match="Injected interruption"):
            apply(driver.directory, attempt)
    assert storage(driver.directory).read() == before
    assert driver.task["evidence"] == evidence
    orphan = driver.directory / "runs" / driver.state["run_id"] / "tasks/TASK-two" / str(driver.task["attempt"]) / "interrupted-evidence.json"
    assert artifacts.exists(orphan) == (boundary != "log-before")
    orphan_bytes = artifacts.read_bytes(orphan) if artifacts.exists(orphan) else None
    assert driver.resume()["check_registries"]["TASK-two"]["pending_transition"] is not None
    driver.role("resume-reviewer", "reviewer")
    assert_rejected(driver, "required_checks", "review_start", {"role_id": "resume-reviewer"})
    # Recovery runs new evidence; its criterion conclusion has a separate verifier.
    assert driver.verify("recovery-verifier")["outcome"] == "passed"
    conclusion = driver.task["verification_results"][-1]
    assert conclusion["role_id"] == "recovery-verifier"
    assert driver.state["roles"][conclusion["role_id"]]["kind"] == "verifier"
    assert driver.state["roles"]["interrupted-explorer"]["kind"] == "explorer"
    if orphan_bytes is not None:
        assert artifacts.read_bytes(orphan) == orphan_bytes
    assert driver.task["check_registry"].get("confirmed_revision", 0) == 0


@pytest.mark.parametrize("written,native", [
    (False, False), (True, False),
    # A persisted acceptance must survive a lost response without applying twice.
    pytest.param(True, True, marks=pytest.mark.native_state),
])
def test_refactoring_check_transitions_acceptance_confirmation_is_atomic_and_repeatable(removal_checkpoint, monkeypatch, written, native):
    from lib import state
    driver = removal_checkpoint("committed", memory_worktree=not native)
    attempt = event(driver, "accept", {}, "interrupted-acceptance")
    target = type(storage(driver.directory))
    original_write = target.save
    before = storage(driver.directory).read()
    def interrupt(store, value):
        if written:
            original_write(store, value)
        raise OSError("Injected interruption at acceptance state write")
    with monkeypatch.context() as patch:
        patch.setattr(target, "save", interrupt)
        with pytest.raises(OSError, match="Injected interruption"):
            apply(driver.directory, attempt)
    if written:
        assert driver.task["status"] == "accepted"
        assert driver.task["check_registry"]["confirmed_revision"] == driver.task["check_registry"]["revision"]
        after = storage(driver.directory).read()
        assert apply(driver.directory, attempt)["status"] == "accepted"
        assert storage(driver.directory).read() == after
    else:
        assert storage(driver.directory).read() == before
        assert driver.task["status"] == "committing"
        assert driver.task["check_registry"].get("confirmed_revision", 0) == 0
        assert apply(driver.directory, attempt)["status"] == "accepted"
    assert driver.resume()["check_registries"]["TASK-two"]["pending_transition"] is None


def test_refactoring_check_transitions_resume_document_edit_retains_pending_revision(removal_checkpoint):
    driver = removal_checkpoint()
    driver.send("checks_revise", driver.revision())
    path = Path(driver.state["basis"]["change_root"]) / "design.md"
    original = path.read_bytes()
    path.write_bytes(original + b"\nChanged approved basis\n")
    admitted = driver.state["basis"]["head"]
    assert driver.resume()["issues"][0]["reason"] == "execution_dirty"
    assert driver.task["check_registry"].get("confirmed_revision", 0) == 0
    assert driver.state["basis"]["head"] == admitted
    assert path.read_bytes() == original + b"\nChanged approved basis\n"
    path.write_bytes(original)
    result = driver.resume()
    assert result["status"] == "active"
    assert result["check_registries"]["TASK-two"]["pending_transition"] is not None


def test_refactoring_check_transitions_ordinary_work_keeps_its_contract(project):
    driver = AcceptanceDriver(approved_basis(project, "change"))
    assert driver.start()["outcome"] == "baseline_recorded"
    # DEC-verification-result gives ordinary conclusions a registry revision;
    # it does not authorize the refactoring-only checks_revise operation.
    registry = deepcopy(driver.task["check_registry"])
    assert registry["revision"] == 1
    assert_rejected(driver, "revision_work_kind", "checks_revise", {})
    assert driver.task["check_registry"] == registry
    assert "transition" not in registry
    assert selected(driver.state, driver.task) == registry["history"][-1]["checks"]


def test_refactoring_check_transitions_approved_revised_plan_preserves_old_transition_and_route(removal_checkpoint):
    driver = removal_checkpoint()
    project = Path(driver.state['basis']['project_root'])
    driver.send("checks_revise", driver.revision())
    prior = deepcopy(driver.task)
    accepted = deepcopy(driver.state["tasks"]["TASK-one"])
    previous_run = driver.state["run_id"]
    for role in driver.state["roles"].values():
        if role["status"] == "active":
            driver.send("role_result", {"role_id": role["role_id"], "result": "Stopped for approved plan revision",
                                        "trace": "synthetic-unit-test"}, task_id=role["task_id"])
    def revised(documents):
        records = {record["id"]: record for record in documents["tasks"]}
        records["AC-removed"]["expected"] = "The approved direct API has explicit preservation evidence"
        records["CHECK-whole"]["test_description"] = "Inspect the revised direct API contract across all consumers"
    transition_basis(project, revise_documents=revised)
    result = driver.send("revised_plan", {"instruction": {"text": "Execute the synthetically approved revision",
                                                           "source": "synthetic-unit-test"}}, task_id=None)
    assert result["previous_run"] == previous_run
    assert driver.state["basis"]["work_kind"] == "refactoring"
    assert driver.state["tasks"]["TASK-one"] == accepted
    assert driver.task["status"] == "pending"
    assert driver.task["prior_result"]["check_registry"] == prior["check_registry"]
    assert driver.task["test_repair_cycles_started"] == prior["test_repair_cycles_started"]
    assert driver.state["acceptance"]["AC-removed"]["expected"] == "The approved direct API has explicit preservation evidence"
    assert driver.state["verification"]["CHECK-whole"]["test_description"] == "Inspect the revised direct API contract across all consumers"
    assert artifacts.is_file(driver.directory / "runs" / previous_run / "superseded-state.json")
