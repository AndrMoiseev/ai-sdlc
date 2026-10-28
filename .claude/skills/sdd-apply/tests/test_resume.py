from pathlib import Path
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
    assert driver.send("check_run", {"role_id": "new-verifier", "stage": "independent"})["outcome"] == "passed"


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
