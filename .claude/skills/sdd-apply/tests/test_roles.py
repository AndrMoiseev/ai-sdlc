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
