import pytest
from lib.documents import ValidationError
from lib.reviews import required_lenses, review_status
from test_review_records import project, report, write


def test_default_and_added_lens(tmp_path):
    root = project(tmp_path)
    (root / "tasks.md").unlink()
    assert required_lenses(tmp_path) == ["consistency", "simplicity", "premortem"]
    index = tmp_path / "sdd/arch-lenses/index.md"
    write(index, {"schema_version": 1, "lenses": []})
    report(tmp_path, root)
    assert not review_status(tmp_path, root, "documents")["review_status"]["complete"]
    report(tmp_path, root, lens="simplicity")
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert not result["complete"]
    assert result["coverage"]["premortem"] == "missing"
    report(tmp_path, root, lens="premortem", result="incomplete")
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert not result["complete"]
    assert result["coverage"]["premortem"] == "incomplete"
    report(tmp_path, root, lens="premortem")
    assert review_status(tmp_path, root, "documents")["review_status"]["complete"]
    (index.parent / "security.md").write_text("Security")
    write(index, {"schema_version": 1, "lenses": [{"id": "security", "title": "Security", "path": "security.md"}]})
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert result["coverage"] == {"consistency": "completed", "simplicity": "completed", "premortem": "completed", "security": "missing"}
    (root / "tasks.md").write_text("normative\n")
    assert review_status(tmp_path, root, "documents")["review_status"]["required_lenses"] == ["consistency", "simplicity", "premortem", "security", "plan"]


@pytest.mark.parametrize("lens", ["consistency", "simplicity", "premortem", "plan"])
def test_reserved_lens_ids_in_memory(monkeypatch, lens):
    from pathlib import Path
    from types import SimpleNamespace
    import lib.reviews as reviews
    monkeypatch.setattr(Path, "exists", lambda path: True)
    monkeypatch.setattr(reviews, "read_document", lambda path: SimpleNamespace(meta={
        "schema_version": 1, "lenses": [{"id": lens, "title": "Reserved", "path": "index.md"}]}))
    with pytest.raises(ValidationError, match="reserved"):
        required_lenses(Path.cwd())


def test_one_bundle_review_includes_plan_and_one_simplicity(tmp_path):
    # Existing file/parser fixture verifies that structural check modes consume
    # the same persisted review instead of demanding a second simplicity report.
    root = project(tmp_path)
    for lens in ("consistency", "simplicity", "premortem", "plan"):
        report(tmp_path, root, run="bundle", lens=lens)
    before = (root / "review/bundle/simplicity.md").read_bytes()
    result = review_status(tmp_path, root, "plan")
    assert result["errors"] == []
    assert result["review_status"]["required_lenses"] == ["consistency", "simplicity", "premortem", "plan"]
    assert result["review_status"]["coverage"] == dict.fromkeys(("consistency", "simplicity", "premortem", "plan"), "completed")
    report(tmp_path, root, run="bundle", lens="simplicity", result="incomplete")
    assert review_status(tmp_path, root, "plan")["review_status"]["coverage"]["simplicity"] == "incomplete"
    report(tmp_path, root, run="bundle", lens="simplicity")
    for stage in ("documents", "plan"):
        result = review_status(tmp_path, root, stage)
        assert result["errors"] == []
        assert result["review_status"]["complete"]
    assert (root / "review/bundle/simplicity.md").read_bytes() == before


@pytest.mark.parametrize("lenses", [None, [{"id": "consistency", "title": "Bad", "path": "index.md"}], [{"id": "security", "title": "Bad", "path": "../outside.md"}], [{"id": "security", "title": "Bad", "path": "missing.md"}]])
def test_invalid_indices(tmp_path, lenses):
    write(tmp_path / "sdd/arch-lenses/index.md", {"schema_version": 1, "lenses": lenses})
    with pytest.raises(ValidationError):
        required_lenses(tmp_path)
