from lib.common import git


def test_drift_preserved_then_restored(driver, project):
    path = project / "sdd/changes/demo/tasks.md"
    before = path.read_bytes()
    path.write_bytes(before + b"Changed\n")
    result = driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)
    assert result["status"] == "blocked"
    assert result["issues"][0]["reason"] == "normative_drift"
    assert path.read_bytes() == before + b"Changed\n"
    path.write_bytes(before)
    assert driver.send("resume", {"host_trace": "unit-observation", "live_contexts": []}, task_id=None)["status"] == "active"


def test_lost_author_successor_preserves_work(driver, project):
    driver.start()
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
