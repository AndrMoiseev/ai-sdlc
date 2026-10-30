import json
from pathlib import Path
import pytest
from lib import artifact_storage as artifacts


def test_done_is_not_acceptance(execution_checkpoint):
    driver = execution_checkpoint("started")
    state = driver.state
    packet = json.loads(artifacts.read_text(driver.directory / "runs" / state["run_id"] / "roles/author.json"))
    assert "approved_documents" not in packet
    assert packet["sources"] == {name: str(Path(state["basis"]["change_root"]) / name)
                                 for name in ("design.md", "proposal.md", "tasks.md", "specs/demo/spec.md")}
    assert "basis" not in packet
    assert packet["project_root"] == state["basis"]["project_root"]
    driver.send("role_result", {"role_id": "author", "result": "DONE", "trace": "synthetic"})
    assert driver.task["status"] == "running"
    assert driver.task["commits"] == []


def test_context_independence_and_review(execution_checkpoint):
    driver = execution_checkpoint("started")
    with pytest.raises(ValueError, match="share"):
        driver.role("fake-reviewer", "reviewer", "author")
    driver.freeze()
    driver.verify()
    assert driver.review()["status"] == "integrating"
    assert driver.task["review_rounds_started"] == 1


def test_missing_host_capability(driver):
    with pytest.raises(ValueError, match="unavailable"):
        driver.send("role_register", {"role_id": "a", "kind": "executor", "context_id": "ctx", "fresh": True, "host": "codex", "launch_ref": "fixture", "capabilities": {"fresh_context": False}})


def test_explorer_research_null_scope_without_final_registry(driver):
    response = driver.explorer("research", task_id=None)
    packet = json.loads(artifacts.read_text(Path(response["packet"])))
    assert packet["task"] is None and "checks" not in packet
    assert packet["assignment"]["kind"] == "research"
    with pytest.raises(ValueError, match="Research result"):
        driver.send("role_result", {"role_id": "research", "result": "DONE", "trace": "unit"}, task_id=None)
    result = {"kind": "research", "answer": "The fixture has one task", "references": ["tasks.md"],
              "inspected_scope": ["tasks.md"], "limitations": [], "assumptions": [], "questions": []}
    driver.send("role_result", {"role_id": "research", "result": result, "trace": "unit"}, task_id=None)
    assert driver.state["roles"]["research"]["result"] == result


def test_explorer_context_can_continue_own_task_but_not_change_role(execution_checkpoint):
    driver = execution_checkpoint("started")
    driver.explorer("research")
    driver.send("role_result", {"role_id": "research", "result": {"kind": "research", "answer": "Ready",
        "references": [], "inspected_scope": ["check.py"], "limitations": [], "assumptions": [], "questions": []}, "trace": "unit"})
    with pytest.raises(ValueError, match="share"):
        driver.explorer("other-scope", task_id=None, context="research")
    driver.freeze()
    driver.explorer("self-explorer", "self", context="research")
    assert driver.send("check_run", {"role_id": "self-explorer", "stage": "self"})["outcome"] == "passed"
    driver.send("role_result", {"role_id": "self-explorer", "result": "DONE", "trace": "unit"})
    driver.explorer("independent-explorer", "independent", context="research")
    assert driver.send("check_run", {"role_id": "independent-explorer", "stage": "independent"})["outcome"] == "passed"
    for kind in ("executor", "verifier", "reviewer"):
        with pytest.raises(ValueError, match="share"):
            driver.role("forbidden-" + kind, kind, context="research")


@pytest.mark.parametrize("stage", ["baseline", "self", "independent", "integration"])
@pytest.mark.parametrize("kind", ["executor", "verifier", "reviewer"])
def test_old_roles_cannot_execute_commands(execution_checkpoint, monkeypatch, stage, kind):
    from lib import verification
    driver = execution_checkpoint("started")
    role = "author" if kind == "executor" else "old-role"
    if kind != "executor":
        driver.role(role, kind)
    def unexpected(*args):
        pytest.fail("Unauthorized role reached command runner")
    monkeypatch.setattr(verification.check_runner, "run_command", unexpected)
    with pytest.raises(ValueError, match="explorer"):
        driver.send("check_run", {"role_id": role, "stage": stage})


def test_explorer_assignment_rejects_scope_stage_stale_registry_and_capability(execution_checkpoint):
    from copy import deepcopy
    driver = execution_checkpoint("started")
    driver.freeze()
    role = driver.explorer("good", "independent")["role"]
    for field, value in (("check_ids", []), ("registry_revision", 100)):
        assignment = deepcopy(role["assignment"])
        assignment[field] = value
        assignment["id"] = "bad"
        with pytest.raises(ValueError):
            driver.explorer("bad", "independent", assignment=assignment)
    assignment = deepcopy(role["assignment"])
    assignment.update(id="foreign")
    assignment["scope"]["task"] = "TASK-foreign"
    with pytest.raises(ValueError, match="scope"):
        driver.explorer("foreign", "independent", assignment=assignment)
    with pytest.raises(ValueError, match="capability unavailable"):
        driver.explorer("unavailable", "independent", capabilities={"fresh_context": True, "observations": {}})
    with pytest.raises(ValueError, match="stage"):
        driver.send("check_run", {"role_id": "good", "stage": "self"})


def test_lost_run_research_successor_does_not_require_final_registry(driver):
    driver.explorer("research", task_id=None)
    driver.send("resume", {"host_trace": "synthetic lost research context", "live_contexts": []}, task_id=None)
    driver.explorer("successor", task_id=None, successor_of="research")
    result = driver.send("resume", {"host_trace": "synthetic fresh research successor", "live_contexts": ["successor"],
        "resolutions": [{"reason": "lost_role", "task_id": None, "role_id": "research", "successor": "successor",
                         "evidence": "Resume bounded research without a final registry"}]}, task_id=None)
    assert result["status"] == "active"
    assert "final_checks" not in driver.state
    assert driver.state["roles"]["research"]["status"] == "lost"

def test_removed_final_role_cannot_register():
    from lib.roles import transition
    from lib.common import Rejected
    payload = {"role_id": "removed", "kind": "final_verifier", "context_id": "unused",
               "fresh": True, "host": "codex", "launch_ref": "unit", "capabilities": {}}
    with pytest.raises(Rejected) as error:
        transition({"roles": {}}, {"plan": {"id": "TASK-one"}},
                   {"type": "role_register", "payload": payload}, None)
    assert error.value.code == "fresh_role"


@pytest.mark.parametrize("event_type", ["check_run", "procedure_begin", "verification_result"])
def test_removed_final_stage_rejects_before_io(event_type):
    from lib import verification, verification_results
    from lib.common import Rejected
    operation = verification_results if event_type == "verification_result" else verification
    with pytest.raises(Rejected) as error:
        operation.transition({}, {}, {"type": event_type, "payload": {"stage": "final"}}, None)
    assert error.value.code in {"check_stage", "verification_stage"}


def test_run_scope_check_registration_is_removed():
    from lib.verification import transition
    from lib.common import Rejected
    with pytest.raises(Rejected) as error:
        transition({}, None, {"type": "checks_register", "payload": {}}, None)
    assert error.value.code == "task_required"
