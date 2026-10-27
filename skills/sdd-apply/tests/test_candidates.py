from lib import artifact_storage as artifacts
from lib.state_storage import storage
import json
from copy import deepcopy
from pathlib import Path
import pytest
from lib.candidates import resolve, same
from lib.common import digest, write_json
from lib.state import seal, save
from lib.verification import current


def frozen(driver, project):
    driver.start()
    (driver.root / "result.txt").write_text("done")
    driver.freeze()
    return driver.task["candidate"]


def test_candidate_uses_commit_and_only_change_documents(driver, project):
    from repository_support import stage, commit
    for number in range(100):
        (project / f"existing-{number}.txt").write_text(str(number))
    stage(project, ".")
    commit(project, "Unrelated tracked source collection")
    from lib.repository import repository
    driver.send("resume", {"host_trace": "synthetic fixture", "live_contexts": [], "resolutions": [
        {"reason": "execution_head_changed", "head": repository(project).head(), "evidence": "Fixture source collection",
         "instruction": {"text": "Accept source collection", "source": "synthetic-user"}}]}, task_id=None)
    reference = frozen(driver, project)
    payload = resolve(driver.state, reference)
    assert reference["candidate_id"] == "candidate-" + digest(payload)
    assert reference["sha256"] == digest(payload)
    assert payload["source"]["commit"]
    assert not payload["source"]["dirty_paths"]
    assert all(name.startswith("sdd/changes/demo/") for name in payload["source"]["files"])
    assert not any("execution/" in name for name in payload["source"]["files"])
    role = driver.role("verifier", "verifier")
    packet = json.loads(artifacts.read_text(role["packet"]))
    assert packet["candidate"] == reference
    assert packet["execution_directory"] == str(driver.directory)
    assert packet["paths"] == driver.task["paths"]
    driver.verify()
    assert all(item["candidate"] == reference for item in driver.task["evidence"])
    assert len(artifacts.paths(driver.directory / "candidates", "*.json")) == 1
    assert driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["verifier"]}, task_id=None)["status"] == "active"


@pytest.mark.parametrize("damage", ["missing", "changed", "invalid"])
def test_missing_or_corrupt_candidate_blocks_review_without_recreating_it(execution_checkpoint, damage):
    driver = execution_checkpoint("verified")
    reference = driver.task["candidate"]
    driver.role("reviewer", "reviewer")
    path = driver.directory / reference["path"]
    if damage == "missing":
        artifacts.remove(path)
    elif damage == "invalid":
        artifacts.write(path, "invalid json")
    else:
        payload = json.loads(artifacts.read_bytes(path))
        payload["source"]["files"] = {}
        write_json(path, payload)
    before = storage(driver.directory).read()
    with pytest.raises(ValueError, match="Candidate artifact"):
        same(driver.state, reference, dict(reference))
    with pytest.raises(ValueError, match="Candidate artifact"):
        driver.send("review_start", {"role_id": "reviewer"})
    assert storage(driver.directory).read() == before
    if damage == "missing":
        assert not artifacts.exists(path)


@pytest.mark.parametrize("field,value", [("path", "../outside.json"), ("root", "forged-root"),
                                        ("candidate_id", "forged-id"), ("sha256", "0" * 64)])
def test_review_rejects_forged_reference(execution_checkpoint, field, value):
    driver = execution_checkpoint("reviewing")
    reference = driver.task["candidate"]
    with pytest.raises(ValueError):
        driver.send("review_result", {"role_id": "reviewer", "candidate": {**reference, field: value},
            "verdict": "pass", "findings": [], "test_integrity": "preserved", "trace": "unit-test"})
    assert driver.task["status"] == "reviewing"


@pytest.mark.parametrize("changed", ["source", "registry", "basis"])
def test_compact_candidate_detects_each_freshness_input(execution_checkpoint, changed):
    driver = execution_checkpoint("frozen")
    project = driver.root
    state = driver.state
    task = state["tasks"]["TASK-one"]
    artifacts_before = set(artifacts.paths(driver.directory / "candidates"))
    if changed == "source":
        (project / "result.txt").write_text("changed")
    elif changed == "registry":
        task["checks"][0]["configuration"] = {"changed": True}
    else:
        state["basis"]["plan_commit"] = "0" * 40
    with pytest.raises(ValueError, match="changed|before verification"):
        current(state, task)
    assert set(artifacts.paths(driver.directory / "candidates")) == artifacts_before


def test_inline_state_evidence_and_review_remain_usable(execution_checkpoint):
    driver = execution_checkpoint("verified")
    reference = driver.task["candidate"]
    state = driver.state
    task = state["tasks"]["TASK-one"]
    inline = resolve(state, reference)
    task["candidate"] = deepcopy(inline)
    for item in task["evidence"]:
        item["candidate"] = deepcopy(inline)
    seal(state)
    save(driver.directory, state)
    assert same(driver.state, reference, inline)
    role = driver.role("reviewer", "reviewer")
    packet = json.loads(artifacts.read_text(role["packet"]))
    assert packet["candidate"] == reference
    result = driver.send("review_start", {"role_id": "reviewer"})
    assert result["candidate"] == reference
    driver.send("review_result", {"role_id": "reviewer", "candidate": reference,
        "verdict": "pass", "findings": [], "test_integrity": "preserved", "trace": "unit-test"})
    driver.integrate()
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"


def test_parallel_packet_links_machine_worktree_inventory(basis, tmp_path):
    from conftest import Driver
    driver = Driver(basis)
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    registered = driver.task["worktree"]
    role = driver.role("author", "executor")
    packet = json.loads(artifacts.read_text(role["packet"]))
    assert packet["worktree"] == {key: value for key, value in registered.items()
                                   if key not in {"snapshot", "inventory"}}
    assert packet["worktree_state"] == {"path": "state.json", "task_id": "TASK-one"}
    assert driver.task["worktree"] == registered
