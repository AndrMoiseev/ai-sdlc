"""Prepared states retain authentic hashes and cannot leak test mutations."""
from pathlib import Path

from lib.repository import repository
from lib.verification import current
from repository_support import stage, commit


def test_checkpoint_restores_files_history_index_and_nested_repository_state(execution_checkpoint):
    driver = execution_checkpoint("verified")
    before = driver.state
    root = Path(before["basis"]["project_root"])
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
