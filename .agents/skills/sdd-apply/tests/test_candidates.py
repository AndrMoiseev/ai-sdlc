from lib import artifact_storage as artifacts
import json


def test_execution_records_no_candidate_artifacts_or_references(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    assert "candidate" not in driver.task
    assert not artifacts.paths(driver.directory / "candidates", "*.json")
    assert all("candidate" not in item for field in ("evidence", "reviews", "commits")
               for item in driver.task[field])
    for item in driver.task["evidence"]:
        log = json.loads(artifacts.read_text(driver.directory / item["log"]))
        assert "candidate" not in log
    packet = json.loads(artifacts.read_text(driver.role("observer", "verifier")["packet"]))
    assert "candidate" not in packet
    assert all("candidate" not in item for item in packet["prior_commits"])


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
