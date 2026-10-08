from lib.snapshots import snapshot
from lib.reviews import review_status
from test_review_records import project, report


def test_bytes_membership_stages_and_exclusions(tmp_path):
    root = project(tmp_path)
    base = snapshot(tmp_path, "demo", "documents")
    assert [e["path"] for e in base] == sorted(e["path"] for e in base)
    assert len(snapshot(tmp_path, "demo", "plan")) == len(base) + 1
    (root / "state.md").write_text("excluded")
    (root / "notes.md").write_text("excluded")
    assert snapshot(tmp_path, "demo", "documents") == base
    (root / "design.md").write_bytes(b"normative\r\n")
    assert snapshot(tmp_path, "demo", "documents") != base
    (root / "design.md").write_bytes(b"normative\n")
    other = root / "specs/other/spec.md"
    other.parent.mkdir()
    other.write_text("new")
    assert len(snapshot(tmp_path, "demo", "documents")) == len(base) + 1
    other.unlink()
    assert snapshot(tmp_path, "demo", "documents") == base


def test_race_stays_stale_after_reversion(tmp_path):
    root = project(tmp_path)
    original = (root / "design.md").read_bytes()
    (root / "design.md").write_text("changed")
    after = snapshot(tmp_path, "demo", "documents")
    (root / "design.md").write_bytes(original)
    report(tmp_path, root, after=after)
    assert review_status(tmp_path, root, "documents")["review_status"]["coverage"]["consistency"] == "stale"
