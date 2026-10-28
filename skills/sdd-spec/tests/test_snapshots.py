"""The retired snapshot API never supplies plausible legacy approval evidence."""
import pytest
from lib.documents import InputError
from lib.snapshots import snapshot
from lib.reviews import review_status
from test_review_records import project, report


@pytest.mark.parametrize("stage", ["documents", "plan"])
def test_snapshot_requires_explicit_migration_without_writes(tmp_path, stage):
    root = project(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(InputError) as raised:
        snapshot(tmp_path, "demo", stage)
    assert raised.value.code == "migration_required"
    assert "checkpoint.py inspect" in str(raised.value)
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_review_commit_is_immutable_during_worktree_changes(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root)
    (root / "design.md").write_text("Uncommitted work")
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert result["reports"]["run-one/consistency"]["reviewed_commit"] == "a" * 40
    assert result["coverage"]["consistency"] == "completed"