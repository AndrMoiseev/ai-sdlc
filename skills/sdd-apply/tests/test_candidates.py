import json
from copy import deepcopy
from pathlib import Path
import pytest
from lib.candidates import resolve, same
from lib.common import digest, write_json
from lib.state import seal
from lib.verification import current


def frozen(driver, project):
    driver.start()
    (project / "result.txt").write_text("done")
    driver.freeze()
    return driver.task["candidate"]


def test_candidate_snapshot_is_deduplicated_in_packets_and_evidence(driver, project):
    for number in range(100):
        (project / f"existing-{number}.txt").write_text(str(number))
    reference = frozen(driver, project)
    payload = resolve(driver.state, reference)
    assert reference["candidate_id"] == "candidate-" + digest(payload)
    assert reference["sha256"] == digest(payload)
    assert len(payload["source"]["files"]) > 100
    assert len(json.dumps(reference)) < len(json.dumps(payload)) / 10
    role = driver.role("verifier", "verifier")
    packet = json.loads(Path(role["packet"]).read_text())
    assert packet["candidate"] == reference
    assert packet["execution_directory"] == str(driver.directory)
    assert packet["paths"] == driver.task["paths"]
    driver.verify()
    assert all(item["candidate"] == reference for item in driver.task["evidence"])
    assert len(list((driver.directory / "candidates").glob("*.json"))) == 1
    assert driver.send("resume", {"host_trace": "unit-observation", "live_contexts": ["verifier"]}, task_id=None)["status"] == "active"


@pytest.mark.parametrize("damage", ["missing", "changed", "invalid"])
def test_missing_or_corrupt_candidate_blocks_review_without_recreating_it(driver, project, damage):
    reference = frozen(driver, project)
    driver.verify()
    driver.role("reviewer", "reviewer")
    path = driver.directory / reference["path"]
    if damage == "missing":
        path.unlink()
    elif damage == "invalid":
        path.write_text("invalid json")
    else:
        payload = json.loads(path.read_text())
        payload["source"]["files"] = {}
        write_json(path, payload)
    before = (driver.directory / "state.json").read_bytes()
    with pytest.raises(ValueError, match="Candidate artifact"):
        driver.send("review_start", {"role_id": "reviewer"})
    assert (driver.directory / "state.json").read_bytes() == before
    if damage == "missing":
        assert not path.exists()


@pytest.mark.parametrize("field,value", [("path", "../outside.json"), ("root", "forged-root"),
                                        ("candidate_id", "forged-id"), ("sha256", "0" * 64)])
def test_review_rejects_forged_reference(driver, project, field, value):
    reference = frozen(driver, project)
    driver.verify()
    driver.role("reviewer", "reviewer")
    driver.send("review_start", {"role_id": "reviewer"})
    with pytest.raises(ValueError):
        driver.send("review_result", {"role_id": "reviewer", "candidate": {**reference, field: value},
            "verdict": "pass", "findings": [], "test_integrity": "preserved", "trace": "unit-test"})
    assert driver.task["status"] == "reviewing"


@pytest.mark.parametrize("changed", ["source", "registry", "basis"])
def test_compact_candidate_detects_each_freshness_input(driver, project, changed):
    frozen(driver, project)
    state = driver.state
    task = state["tasks"]["TASK-one"]
    if changed == "source":
        (project / "result.txt").write_text("changed")
    elif changed == "registry":
        task["checks"][0]["configuration"] = {"changed": True}
    else:
        state["basis"]["manifest"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="changed"):
        current(state, task)


def test_inline_state_evidence_and_review_remain_usable(driver, project):
    reference = frozen(driver, project)
    driver.verify()
    state = driver.state
    task = state["tasks"]["TASK-one"]
    inline = resolve(state, reference)
    task["candidate"] = deepcopy(inline)
    for item in task["evidence"]:
        item["candidate"] = deepcopy(inline)
    seal(state)
    write_json(driver.directory / "state.json", state)
    assert same(driver.state, reference, inline)
    role = driver.role("reviewer", "reviewer")
    packet = json.loads(Path(role["packet"]).read_text())
    assert packet["candidate"] == reference
    result = driver.send("review_start", {"role_id": "reviewer"})
    assert result["candidate"] == reference
    driver.send("review_result", {"role_id": "reviewer", "candidate": reference,
        "verdict": "pass", "findings": [], "test_integrity": "preserved", "trace": "unit-test"})
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"


def test_parallel_packet_links_machine_worktree_inventory(basis, tmp_path):
    from conftest import Driver
    driver = Driver(basis, parallel=True)
    driver.send("worktree_create", {"workspace": str(tmp_path / "worktrees")})
    registered = driver.task["worktree"]
    role = driver.role("author", "executor")
    packet = json.loads(Path(role["packet"]).read_text())
    assert packet["worktree"] == {key: value for key, value in registered.items()
                                   if key not in {"snapshot", "inventory"}}
    assert packet["worktree_state"] == {"path": "state.json", "task_id": "TASK-one"}
    assert driver.task["worktree"] == registered
