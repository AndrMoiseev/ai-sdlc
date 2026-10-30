import pytest
from lib.documents import ValidationError
from lib.reviews import required_lenses, review_status
from test_review_records import project, report, write


def test_default_and_added_lens(tmp_path):
    root = project(tmp_path)
    assert required_lenses(tmp_path) == ["consistency", "simplicity"]
    index = tmp_path / "sdd/arch-lenses/index.md"
    write(index, {"schema_version": 1, "lenses": []})
    report(tmp_path, root)
    assert not review_status(tmp_path, root, "documents")["review_status"]["complete"]
    report(tmp_path, root, lens="simplicity")
    assert review_status(tmp_path, root, "documents")["review_status"]["complete"]
    (index.parent / "security.md").write_text("Security")
    write(index, {"schema_version": 1, "lenses": [{"id": "security", "title": "Security", "path": "security.md"}]})
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert result["coverage"] == {"consistency": "completed", "simplicity": "completed", "security": "missing"}


@pytest.mark.parametrize("lens", ["consistency", "simplicity", "plan"])
def test_reserved_lens_ids_in_memory(monkeypatch, lens):
    from pathlib import Path
    from types import SimpleNamespace
    import lib.reviews as reviews
    monkeypatch.setattr(Path, "exists", lambda path: True)
    monkeypatch.setattr(reviews, "read_document", lambda path: SimpleNamespace(meta={
        "schema_version": 1, "lenses": [{"id": lens, "title": "Reserved", "path": "index.md"}]}))
    with pytest.raises(ValidationError, match="reserved"):
        required_lenses(Path.cwd())


def test_simplicity_coverage_is_separate_for_each_stage(tmp_path):
    # Persisted report paths/stages must route independently; reuse the existing
    # filesystem fixture and injected Git adapter instead of another CLI/Git run.
    root = project(tmp_path)
    report(tmp_path, root, run="documents", lens="consistency")
    report(tmp_path, root, run="documents", lens="simplicity")
    report(tmp_path, root, run="plan", lens="plan", stage="plan")
    before = (root / "review/documents/simplicity.md").read_bytes()
    result = review_status(tmp_path, root, "plan")
    assert result["errors"] == []
    assert result["review_status"]["required_lenses"] == ["plan", "simplicity"]
    assert result["review_status"]["coverage"] == {"plan": "completed", "simplicity": "missing"}
    report(tmp_path, root, run="plan", lens="simplicity", stage="plan", result="incomplete")
    assert review_status(tmp_path, root, "plan")["review_status"]["coverage"]["simplicity"] == "incomplete"
    report(tmp_path, root, run="plan", lens="simplicity", stage="plan")
    for stage in ("documents", "plan"):
        result = review_status(tmp_path, root, stage)
        assert result["errors"] == []
        assert result["review_status"]["complete"]
    assert (root / "review/documents/simplicity.md").read_bytes() == before


@pytest.mark.parametrize("lenses", [None, [{"id": "consistency", "title": "Bad", "path": "index.md"}], [{"id": "security", "title": "Bad", "path": "../outside.md"}], [{"id": "security", "title": "Bad", "path": "missing.md"}]])
def test_invalid_indices(tmp_path, lenses):
    write(tmp_path / "sdd/arch-lenses/index.md", {"schema_version": 1, "lenses": lenses})
    with pytest.raises(ValidationError):
        required_lenses(tmp_path)
