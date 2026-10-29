from pathlib import Path
from copy import deepcopy
import pytest


def test_resume_requires_clean_main_tree_and_preserves_document_edits(driver, project):
    path = project / "sdd/changes/demo/tasks.md"
    before = path.read_bytes()
    path.write_bytes(before + b"Changed\n")
    result = driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    assert result["status"] == "blocked"
    assert result["issues"][0]["reason"] == "execution_dirty"
    assert path.read_bytes() == before + b"Changed\n"
    path.write_bytes(before)
    assert driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)["status"] == "active"


def test_resume_external_head_needs_exact_explicit_acceptance(driver, project):
    from repository_support import stage, commit
    from lib.repository import repository
    admitted = driver.state["basis"]
    (project / "external.txt").write_text("external change")
    stage(project, "external.txt")
    commit(project, "External change")
    payload = {"host_trace": "unit-observation", "live_contexts": []}
    assert driver.send("resume", payload, task_id=None)["issues"][0]["reason"] == "execution_head_changed"
    resolution = dict(reason="execution_head_changed", head=repository(project).head(),
                      evidence="Inspected external commit", instruction={"text": "Accept this source state", "source": "synthetic-user"})
    with pytest.raises(ValueError, match="actual user response"):
        driver.send("resume", {**payload, "resolutions": [{**resolution, "head": "0" * 40}]}, task_id=None)
    assert driver.send("resume", {**payload, "resolutions": [resolution]}, task_id=None)["status"] == "active"
    assert driver.state["basis"] == admitted


def test_lost_author_successor_preserves_work(execution_checkpoint):
    driver = execution_checkpoint("started")
    project = driver.root
    (project / "result.txt").write_text("unfinished")
    result = driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    assert result["status"] == "blocked"
    assert driver.state["roles"]["author"]["status"] == "lost"
    driver.send("role_register", {"role_id": "successor", "kind": "executor", "context_id": "new-context", "fresh": True, "host": "codex", "launch_ref": "unit-launch", "capabilities": {"fresh_context": True}, "successor_of": "author"})
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["new-context"], "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "evidence": "successor ready", "successor": "successor"}]}, task_id=None)
    assert driver.task["executor"] == "successor"
    assert driver.task["status"] == "running"
    assert (project / "result.txt").read_text() == "unfinished"


def test_spec_conflict_only_execution_files(driver, project):
    paths = list((project / "sdd/changes/demo").glob("*.md"))
    before = {p: p.read_bytes() for p in paths}
    result = driver.send("spec_conflict", {"reproduction": "input x produces y", "criteria": ["AC-one"], "contract": "incompatible requirements"})
    assert result["return_to"] == "sdd-spec"
    assert before == {p: p.read_bytes() for p in paths}


def successor(driver, role_id, kind, predecessor):
    driver.send("role_register", {"role_id": role_id, "kind": kind,
        "context_id": role_id, "fresh": True, "host": "codex",
        "launch_ref": "synthetic-unit-test", "capabilities": {"fresh_context": True},
        "successor_of": predecessor})


@pytest.mark.parametrize("separate_observations", [False, True])
def test_multiple_lost_roles_recover_individually(execution_checkpoint, separate_observations):
    driver = execution_checkpoint("started")
    project = driver.root
    (project / "result.txt").write_text("unfinished")
    driver.role("verifier", "verifier")
    driver.send("resume", {"host_trace": "unit-observation",
        "live_contexts": ["verifier"] if separate_observations else []}, task_id=None)
    if separate_observations:
        driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    assert driver.task["before_block"] == "running"
    assert {b["role_id"] for b in driver.task["blockers"]} == {"author", "verifier"}

    successor(driver, "new-author", "executor", "author")
    result = driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["new-author"],
        "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "role_id": "author",
                         "successor": "new-author", "evidence": "fresh executor ready"}]}, task_id=None)
    assert result["status"] == "blocked"
    assert driver.task["status"] == "blocked"
    assert driver.task["executor"] == "new-author"
    assert [b["role_id"] for b in driver.task["blockers"]] == ["verifier"]
    assert [b["role_id"] for b in driver.state["blockers"]] == ["verifier"]

    successor(driver, "new-verifier", "verifier", "verifier")
    # Older clients can omit role_id; successor_of identifies exactly one loss.
    result = driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["new-author", "new-verifier"],
        "resolutions": [{"reason": "lost_role", "task_id": "TASK-one",
                         "successor": "new-verifier", "evidence": "fresh verifier ready"}]}, task_id=None)
    assert result["status"] == "active"
    assert driver.task["status"] == "running"
    assert driver.task["blockers"] == []
    assert (project / "result.txt").read_text() == "unfinished"
    driver.send("role_result", {"role_id": "new-author", "result": "DONE", "trace": "unit-test"})
    driver.send("candidate")
    assert driver.run_checks("independent")["outcome"] == "passed"


def test_lost_role_resolution_must_match_predecessor_and_kind(execution_checkpoint):
    driver = execution_checkpoint("started")
    driver.role("verifier", "verifier")
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    successor(driver, "wrong-kind", "reviewer", "author")
    successor(driver, "new-verifier", "verifier", "verifier")
    for role_id, new_role in [("author", "wrong-kind"), ("author", "new-verifier")]:
        with pytest.raises(ValueError) as exc:
            driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["wrong-kind", "new-verifier"],
                "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "role_id": role_id,
                    "successor": new_role, "evidence": "incorrect successor"}]}, task_id=None)
        assert exc.value.code == "successor_required"
    assert len(driver.task["blockers"]) == 2


def test_reviewer_successor_continues_reserved_round_after_two_losses(execution_checkpoint):
    driver = execution_checkpoint("reviewing")
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    assert driver.task["before_block"] == "reviewing"
    successor(driver, "new-reviewer", "reviewer", "reviewer")
    successor(driver, "new-verifier", "verifier", "verifier")
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["new-reviewer", "new-verifier"],
        "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "role_id": old,
            "successor": new, "evidence": "fresh role ready"}
            for old, new in [("reviewer", "new-reviewer"), ("verifier", "new-verifier")]]}, task_id=None)
    assert driver.task["status"] == "reviewing"
    assert driver.task["review_rounds_started"] == 1
    result = driver.send("review_result", {"role_id": "new-reviewer",
        "verdict": "pass", "findings": [], "test_integrity": "commands and assertions preserved", "trace": "unit-test"})
    assert result["status"] == "integrating"


def test_replacing_another_reviewer_does_not_steal_reserved_round(execution_checkpoint):
    driver = execution_checkpoint("reviewing")
    driver.role("other-reviewer", "reviewer")
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["verifier", "reviewer"]}, task_id=None)
    successor(driver, "replacement", "reviewer", "other-reviewer")
    driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["verifier", "reviewer", "replacement"],
        "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "role_id": "other-reviewer",
            "successor": "replacement", "evidence": "fresh role ready"}]}, task_id=None)
    assert driver.task["status"] == "reviewing"
    assert driver.task["active_reviewer"] == "reviewer"


@pytest.mark.parametrize("scope", ["task", "final"])
def test_lost_explorer_abandons_procedure_preserving_attempt_budget(execution_checkpoint, monkeypatch, scope):
    """AC-explorer-resume: task/run recovery uses memory state and a fake clock."""
    from test_budgets import procedure_deadline_setup, timed_explorer
    from lib import explorer_assignments
    from lib.state_storage import storage
    driver, task_id, stage = procedure_deadline_setup(execution_checkpoint, scope)
    clock = [1000.0]
    monkeypatch.setattr(explorer_assignments.time, "time", lambda: clock[0])
    monkeypatch.setattr(explorer_assignments.time, "monotonic", lambda: clock[0])
    timed_explorer(driver, task_id, stage, "lost-explorer")
    first = driver.send("procedure_begin", {"role_id": "lost-explorer", "stage": stage,
                        "check_id": "timed-procedure"}, task_id=task_id)
    before = driver.state
    live = [role["context_id"] for role in before["roles"].values()
            if role["status"] == "active" and role["role_id"] != "lost-explorer"]
    driver.send("resume", {"host_trace": "synthetic lost explorer", "live_contexts": live}, task_id=None)
    driver.explorer("successor-explorer", stage, task_id=task_id, successor_of="lost-explorer")
    resolution = {"reason": "lost_role", "task_id": task_id, "role_id": "lost-explorer",
                  "successor": "successor-explorer", "evidence": "Synthetic successor ready"}
    payload = {"host_trace": "synthetic recovery", "live_contexts": live + ["successor-explorer"],
               "resolutions": [resolution]}
    saved = storage(driver.directory).read()
    with pytest.raises(ValueError, match="every unfinished"):
        driver.send("resume", payload, task_id=None)
    assert storage(driver.directory).read() == saved
    resolution["abandon_procedures"] = ["timed-procedure"]
    driver.send("resume", payload, task_id=None)
    state = driver.state
    holder = state["tasks"][task_id] if task_id else state["final_checks"]
    assert holder["procedures"] == {}
    assert holder["evidence"][-1]["outcome"] == "abandoned"
    assert state["roles"]["lost-explorer"]["check_budget"] == before["roles"]["lost-explorer"]["check_budget"]
    assert driver.task["test_repair_cycles_started"] == before["tasks"]["TASK-one"]["test_repair_cycles_started"]
    with pytest.raises(ValueError):
        driver.send("procedure_result", {"role_id": "successor-explorer", "check_id": "timed-procedure",
                    "outcome": "passed", "steps": ["Cannot complete predecessor attempt"], "trace": "synthetic"}, task_id=task_id)
    clock[0] += 4
    fresh = driver.send("procedure_begin", {"role_id": "successor-explorer", "stage": stage,
                        "check_id": "timed-procedure"}, task_id=task_id)
    assert fresh["check_deadline"] == first["check_deadline"]
    assert fresh["remaining_timeout"] == 6
    assert driver.state["roles"]["lost-explorer"]["status"] == "lost"


@pytest.mark.parametrize("checkpoint", ["pending", "accepted"])
def test_lost_task_research_is_reconciled_without_reopening_task(execution_checkpoint, checkpoint):
    """AC-explorer-resume: research liveness applies before and after task execution."""
    driver = execution_checkpoint(checkpoint)
    driver.explorer("research")
    live = [role["context_id"] for role in driver.state["roles"].values()
            if role["status"] == "active" and role["role_id"] != "research"]
    assert driver.send("resume", {"host_trace": "synthetic host", "live_contexts": live}, task_id=None)["status"] == "blocked"
    assert driver.task["status"] == ("accepted" if checkpoint == "accepted" else "pending")
    driver.explorer("replacement", successor_of="research")
    result = driver.send("resume", {"host_trace": "synthetic host", "live_contexts": live + ["replacement"],
        "resolutions": [{"reason": "lost_role", "task_id": "TASK-one", "successor": "replacement", "evidence": "ready"}]}, task_id=None)
    assert result["status"] == "active"


def test_revision_retains_registered_checks_and_conclusions_as_history(execution_checkpoint, monkeypatch):
    """AC-explorer-resume: approved new basis preserves obligations, not freshness."""
    from lib import inputs
    from lib.state_view import compact
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"],
        "additional": [{"id": "project-check", "source": "CI", "criteria": ["AC-one"],
                        "run": driver.task["checks"][0]["run"]}]})
    for role in driver.state["roles"].values():
        if role["status"] == "active":
            driver.send("role_result", {"role_id": role["role_id"], "result": "DONE", "trace": "synthetic"})
    before = driver.state
    basis = deepcopy(before["basis"])
    basis["head"] = "b" * 40
    monkeypatch.setattr(inputs, "validate", lambda *args, **kwargs: deepcopy(basis))
    driver.send("revised_plan", {"instruction": {"text": "Approved revision", "source": "synthetic-user"}}, task_id=None)
    task = driver.task
    for field in ("checks", "inventory", "check_registry", "evidence", "verification_results", "roles",
                  "review_rounds_started", "test_repair_cycles_started", "budget_decisions"):
        assert task[field] == before["tasks"]["TASK-one"][field]
    assert driver.state["run_id"] != before["run_id"]
    assert compact(driver.state)["tasks"]["TASK-one"]["verification"]["independent"]["conclusion"]["status"] == "stale"


@pytest.mark.parametrize("pending", [False, True])
def test_revised_registry_preserves_confirmed_and_pending_records(pending):
    """AC-explorer-resume: registry reconciliation is an in-memory contract."""
    from lib.resume import revised_checks
    plan = {"id": "TASK-one", "scope": [{"module": "core", "paths": ["check.py"]}],
            "test_changes": [{"id": "approved-group", "action": "adapt", "criteria": ["AC-one"], "reason": "Old wording"}],
            "verification": [{"id": "check", "criteria": ["AC-one"],
            "location": "check.py", "run": {"command": ["python", "check.py"]}}]}
    check = {"id": "TASK-one/check", "source": "tasks.md", "criteria": ["AC-one"],
             "location": "check.py", "run": {"command": ["python", "check.py"]}, "setup": None, "cwd": ".", "configuration": {}}
    transition = {"basis": {"test_changes": ["approved-group"]}, "before": [check], "after": [check]} if pending else None
    registry = {"revision": 2, "confirmed_revision": 1 if pending else 2,
                "history": [{"revision": 1, "checks": [check]}, {"revision": 2, "checks": [check]}]}
    if pending:
        registry["transition"] = transition
        registry["history"][-1]["transition"] = transition
    old = {"plan": plan, "checks": [check], "check_registry": registry}
    acceptance = {"id": "AC-one", "task": "TASK-one", "lifetime": "persistent", "expected": "Original wording"}
    state = {"acceptance": {"AC-one": acceptance}}
    basis = {"head": "b" * 40, "work_kind": "refactoring", "acceptance": [acceptance]}
    event = {"type": "revised_plan", "event_id": "revision"}
    assert revised_checks(state, old, plan, basis, event) == old
    clarified_basis, clarified_plan = deepcopy(basis), deepcopy(plan)
    clarified_basis["acceptance"][0]["expected"] = "Approved clarified criterion"
    clarified_plan["verification"][0]["test_description"] = "Approved clarified description"
    clarified_plan["test_changes"][0]["reason"] = "Approved clarified rationale"
    assert revised_checks(state, old, clarified_plan, clarified_basis, event) == old
    changed = deepcopy(plan)
    changed["verification"][0]["run"] = {"command": ["python", "new_check.py"]}
    before = deepcopy(old)
    if pending:
        with pytest.raises(ValueError, match="pending registry transition"):
            revised_checks(state, old, changed, basis, event)
        for field, value in (("task", "TASK-other"), ("lifetime", "transitional"), ("id", "AC-other")):
            incompatible = deepcopy(basis)
            incompatible["acceptance"][0][field] = value
            with pytest.raises(ValueError, match="pending registry transition"):
                revised_checks(state, old, plan, incompatible, event)
        for field, value in (("action", "add"), ("criteria", ["AC-other"])):
            incompatible_plan = deepcopy(plan)
            incompatible_plan["test_changes"][0][field] = value
            with pytest.raises(ValueError, match="pending registry transition"):
                revised_checks(state, old, incompatible_plan, basis, event)
    else:
        result = revised_checks(state, old, changed, basis, event)
        assert result["check_registry"]["confirmed_revision"] == 2
        assert result["check_registry"]["history"][:2] == registry["history"]
        assert result["check_registry"]["history"][-1]["basis_commit"] == basis["head"]
        assert result["check_registry"]["revision"] == 3
    assert old == before


def test_incompatible_pending_revision_rejects_before_archive(execution_checkpoint, monkeypatch):
    """AC-explorer-resume: rejected approved-basis reconciliation has no effects."""
    from lib import inputs, artifact_storage
    from lib.state import seal, save
    from lib.state_storage import storage
    driver = execution_checkpoint("frozen")
    state = driver.state
    task = state["tasks"]["TASK-one"]
    registry = task["check_registry"]
    permission = {"id": "synthetic-approved-group", "action": "adapt", "criteria": ["AC-one"]}
    task["plan"]["test_changes"] = [permission]
    state["basis"]["tasks"][0]["test_changes"] = [permission]
    transition = {"before": deepcopy(task["checks"]), "after": deepcopy(task["checks"]),
                  "basis": {"test_changes": ["synthetic-approved-group"]}}
    registry["transition"] = transition
    registry["history"][-1]["transition"] = transition
    registry["confirmed_revision"] = 0
    save(driver.directory, seal(state))
    basis = deepcopy(state["basis"])
    basis["head"] = "c" * 40
    basis["tasks"][0]["verification"][0]["run"] = {"command": ["python", "replacement.py"]}
    monkeypatch.setattr(inputs, "validate", lambda *args, **kwargs: deepcopy(basis))
    before = storage(driver.directory).read()
    paths = set(artifact_storage.paths(driver.directory))
    with pytest.raises(ValueError, match="pending registry transition"):
        driver.send("revised_plan", {"instruction": {"text": "Approved revised plan", "source": "synthetic-user"}}, task_id=None)
    assert storage(driver.directory).read() == before
    assert set(artifact_storage.paths(driver.directory)) == paths


@pytest.mark.parametrize("change", ["add", "command", "metadata", "collision"])
def test_revised_plan_reconciles_whole_checks_and_preserves_project_registry(project, monkeypatch, change):
    """AC-explorer-resume: memory reducer checks obligations, not just criterion coverage."""
    from conftest import Driver
    from refactoring_fixtures import approved_basis
    from lib import inputs, artifact_storage
    from lib.final_checks import applicable
    from lib.state_storage import storage
    driver = Driver(approved_basis(project))
    command = driver.state["basis"]["verification"][0]["run"]
    driver.send("checks_register", {"inventory": {"instructions": ["AGENTS.md"], "ci": []},
        "additional": [{"id": "CHECK-project", "source": "CI", "criteria": ["AC-result"], "run": command}]}, task_id=None)
    before = driver.state
    approved = deepcopy(before["basis"])
    approved["head"] = "d" * 40
    if change in {"add", "collision"}:
        added = deepcopy(approved["verification"][0])
        added["id"] = "CHECK-added" if change == "add" else "CHECK-project"
        approved["verification"].append(added)
    elif change == "command":
        approved["verification"][0]["run"] = {"command": ["python", "replacement.py"]}
    else:
        approved["verification"][0]["test_description"] = "Approved clearer whole-check description"
    monkeypatch.setattr(inputs, "validate", lambda *args, **kwargs: deepcopy(approved))
    saved = storage(driver.directory).read()
    paths = set(artifact_storage.paths(driver.directory))
    payload = {"instruction": {"text": "Approved whole-check revision", "source": "synthetic-user"}}
    if change == "collision":
        with pytest.raises(ValueError, match="conflicts with a registered project obligation"):
            driver.send("revised_plan", payload, task_id=None)
        assert storage(driver.directory).read() == saved
        assert set(artifact_storage.paths(driver.directory)) == paths
        return
    driver.send("revised_plan", payload, task_id=None)
    state = driver.state
    old, new = before["final_checks"], state["final_checks"]
    checks = {item["id"]: item for item in applicable(state)}
    assert set(checks) == {item["id"] for item in approved["verification"]} | {"CHECK-project"}
    assert checks["CHECK-project"] == next(item for item in old["checks"] if item["id"] == "CHECK-project")
    assert checks["CHECK-whole"]["run"] == approved["verification"][0]["run"]
    assert new["inventory"] == old["inventory"]
    assert new["history"][:old["revision"]] == old["history"]
    assert new["revision"] == old["revision"] + (change != "metadata")
    assert state["run_id"] != before["run_id"]
    if change != "metadata":
        assert new["history"][-1]["basis_commit"] == approved["head"]


def test_whole_registry_revision_retains_prepared_setup_and_proof_history():
    """AC-explorer-resume: unchanged setup/evidence survive additions without I/O."""
    from lib.final_checks import planned_checks, revised_registry
    planned = {"id": "CHECK-whole", "criteria": ["AC-result"], "location": "whole.py",
               "run": {"setup_required": "Prepare whole check"}, "setup_task": "TASK-one"}
    check = planned_checks([planned])[0]
    check["setup"] = {"command": ["python", "whole.py"], "description": "Prepared earlier"}
    project_check = {"id": "project-check", "source": "CI", "criteria": ["AC-result"],
                     "run": {"command": ["python", "ci.py"]}, "setup": None}
    holder = {"checks": [check, project_check], "revision": 1,
              "history": [{"revision": 1, "event_id": "registered", "checks": [check, project_check]}],
              "inventory": {"instructions": [], "ci": ["ci.yml"]},
              "evidence": [{"log": "old-run.json", "outcome": "passed"}],
              "verification_results": [{"id": "old-conclusion", "outcome": "passed"}],
              "procedures": {}, "failures": {}}
    state = {"final_checks": holder, "verification": {"CHECK-whole": planned}, "tasks": {}}
    added = {"id": "CHECK-added", "criteria": ["AC-result"], "location": "extra.py",
             "run": {"command": ["python", "extra.py"]}}
    approved = {"work_kind": "refactoring", "verification": [planned, added], "tasks": [], "head": "e" * 40}
    before = deepcopy(state)
    result = revised_registry(state, approved, {"event_id": "revised", "type": "revised_plan"})
    assert result["checks"][0] == check
    assert result["checks"][-1] == project_check
    for field in ("inventory", "evidence", "verification_results"):
        assert result[field] == holder[field]
    assert result["history"][0] == holder["history"][0]
    assert result["revision"] == 2
    assert state == before
