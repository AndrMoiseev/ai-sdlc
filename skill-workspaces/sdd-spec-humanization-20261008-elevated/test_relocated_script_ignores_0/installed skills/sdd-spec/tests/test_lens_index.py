import pytest
from lib.documents import ValidationError
from lib.reviews import required_lenses, review_status
from test_review_records import project, report, write


def test_default_and_added_lens(tmp_path):
    root = project(tmp_path)
    assert required_lenses(tmp_path) == ["consistency"]
    index = tmp_path / "sdd/arch-lenses/index.md"
    write(index, {"schema_version": 1, "lenses": []})
    report(tmp_path, root)
    assert review_status(tmp_path, root, "documents")["review_status"]["complete"]
    (index.parent / "security.md").write_text("Security")
    write(index, {"schema_version": 1, "lenses": [{"id": "security", "title": "Security", "path": "security.md"}]})
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert result["coverage"] == {"consistency": "completed", "security": "missing"}


@pytest.mark.parametrize("lenses", [None, [{"id": "consistency", "title": "Bad", "path": "index.md"}], [{"id": "security", "title": "Bad", "path": "../outside.md"}], [{"id": "security", "title": "Bad", "path": "missing.md"}]])
def test_invalid_indices(tmp_path, lenses):
    write(tmp_path / "sdd/arch-lenses/index.md", {"schema_version": 1, "lenses": lenses})
    with pytest.raises(ValidationError):
        required_lenses(tmp_path)
