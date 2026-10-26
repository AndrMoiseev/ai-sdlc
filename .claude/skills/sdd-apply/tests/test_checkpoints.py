"""Prepared states retain authentic hashes and cannot leak test mutations."""
from pathlib import Path

from lib.repository import repository
from lib.verification import current
from repository_support import stage, commit


def test_preparation_stops_at_requested_stage_and_discards_mutations_before_advancing(
        project_template, basis_template, repository_seeds, tmp_path_factory,
        repository_backend, state_backend):
    from conftest import execution_checkpoints
    prepared = execution_checkpoints.__wrapped__(
        project_template, basis_template, repository_seeds, tmp_path_factory)
    initial = prepared["started"]
    assert set(prepared.saved) == {"pending", "started"}
    driver = initial.restore(repository_backend, state_backend)
    (driver.root / "check.py").write_text("assert False, 'test-local mutation'\n")
    (driver.root / "unknown.txt").write_text("discard this test's data")
    driver.send("block", {"reason": "test-local", "resume_condition": "restore"})

    frozen = prepared["frozen"].restore(repository_backend, state_backend)
    assert set(prepared.saved) == {"pending", "started", "frozen"}
    assert prepared["started"] is initial
    assert not (frozen.root / "unknown.txt").exists()
    assert frozen.task["status"] == "verifying" and not frozen.state["blockers"]
    assert frozen.verify()["outcome"] == "passed"


def test_checkpoint_restores_files_history_index_and_nested_repository_state(execution_checkpoint):
    driver = execution_checkpoint("verified")
    before = driver.state
    view = driver.task
    view["plan"]["verification"][0]["test_description"] = "mutated view"
    view["evidence"].clear()
    assert driver.task["plan"]["verification"][0]["test_description"] != "mutated view"
    assert driver.task["evidence"]
    root = driver.root
    repo = repository(root)
    head = repo.head()
    (root / "result.txt").write_bytes(b"damaged")
    stage(root, "result.txt")
    commit(root, "test-local commit")
    (root / "unknown.txt").write_bytes(b"test-local file")
    driver.send("block", {"reason": "test-local blocker", "resume_condition": "restore"})
    restored = execution_checkpoint("verified")
    assert restored is not driver and restored.state == before
    assert repository(root).head() == head
    assert repository(root).index_patch() == b""
    assert not (root / "unknown.txt").exists()
    assert (root / "result.txt").read_text() == "verified result\n"
    current(restored.state, restored.task)
    # Candidate bytes, event hashes and revision counters were restored, not
    # regenerated to conceal an invalid prepared state.
    assert restored.verify()["outcome"] == "passed"
