import pytest
from conftest import write_doc
from lib.documents import InputError, ValidationError, read_document, safe_yaml
from lib.paths import contained


@pytest.mark.parametrize("value", ["a: 2026-99-99", "a: 2026-01-01T99:99:99Z", "a: " + "[" * 1000 + "0" + "]" * 1000, "a: " + "9" * 5000])
def test_invalid_scalars_and_deep_yaml_return_structural_errors(value):
    with pytest.raises(ValidationError) as caught:
        safe_yaml(value)
    assert caught.value.code in {"invalid_yaml", "yaml_limit"}


def test_invalid_scalar_is_serializable_validation_error(bundle):
    import json
    from lib.validation import validate_documents
    root, change, _, _ = bundle
    path = change / "specs/feature/spec.md"
    path.write_text(path.read_text().replace("conditions: Input", "conditions: 2026-99-99"))
    result = validate_documents(root, change, "documents")
    assert "invalid_yaml" in {e["code"] for e in result["errors"]}
    json.dumps(result)


def test_oversized_document_rejected(bundle, monkeypatch):
    import lib.documents as documents
    _, change, _, _ = bundle
    monkeypatch.setattr(documents, "MAX_DOCUMENT_CHARS", 10)
    with pytest.raises(ValidationError, match="character limit"):
        read_document(change / "proposal.md")


@pytest.mark.parametrize("yaml", ["x: 1\nx: 2", "x: &a [1]\ny: *a", "x: !!str hello", "x: {<<: {a: 1}}", "x: !custom value"])
def test_unsafe_yaml(yaml):
    with pytest.raises(ValidationError):
        safe_yaml(yaml)


def test_nested_fence_example_not_record(bundle):
    _, change, _, _ = bundle
    path = change / "design.md"
    with path.open("a", encoding="utf-8") as f:
        f.write('````markdown\n### Example\n```yaml\nsdd_record: requirement\nid: REQ-example\n```\n````\n')
    assert read_document(path).records == []


@pytest.mark.parametrize("mutation", [lambda r: r.update(id="REQ-123"), lambda r: r.update(extra=True), lambda r: r.pop("operation"), lambda r: r.update(sdd_record="decision")])
def test_record_contract(bundle, mutation):
    _, change, records, _ = bundle
    mutation(records[0])
    path = write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    with pytest.raises(ValidationError):
        read_document(path)


def test_duplicate_id_and_version(bundle):
    _, change, records, _ = bundle
    path = write_doc(change / "specs/feature/spec.md", "spec", records + [records[0]], capability="feature")
    with pytest.raises(ValidationError, match="duplicate"):
        read_document(path)
    path.write_text(path.read_text().replace("schema_version: 1", "schema_version: 2"))
    with pytest.raises(InputError):
        read_document(path)


@pytest.mark.parametrize("relative", ["../escape", "C:/escape", "/escape", "dir/../../escape", "dir\\escape"])
def test_path_escape(tmp_path, relative):
    with pytest.raises(ValidationError):
        contained(tmp_path, relative)


def test_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit unprivileged symlinks")
    with pytest.raises(ValidationError):
        contained(root, "link/outside")


def test_record_position(bundle):
    _, change, _, _ = bundle
    path = change / "specs/feature/spec.md"
    path.write_text(path.read_text().replace("### Record\n\n", "### Record\n\nIntervening paragraph.\n\n", 1))
    with pytest.raises(ValidationError):
        read_document(path)


def nested_spec(change, records):
    path = write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    text = path.read_text(encoding="utf-8")
    text = text.replace("### Record\n\n```yaml\nsdd_record: requirement", "## Record\n\n```yaml\nsdd_record: requirement")
    path.write_text(text, encoding="utf-8")
    return path


def test_nested_requirements_with_multiple_criteria(bundle):
    _, change, records, _ = bundle
    records += [dict(records[1], id="AC-feature-error"),
                dict(records[0], id="REQ-second"),
                dict(records[1], id="AC-second", requirement="REQ-second")]
    assert read_document(nested_spec(change, records)).records == records


@pytest.mark.parametrize("case", ["wrong_parent", "before_requirement", "outside_requirement", "mixed_levels"])
def test_nested_spec_rejects_misleading_hierarchy(bundle, case):
    _, change, records, _ = bundle
    if case == "wrong_parent":
        records += [dict(records[0], id="REQ-second"), dict(records[1], id="AC-second")]
    elif case == "before_requirement":
        records.reverse()
    path = nested_spec(change, records)
    text = path.read_text(encoding="utf-8")
    if case == "outside_requirement":
        text = text.replace("### Record", "## Other section\n\n### Record")
    elif case == "mixed_levels":
        text += "\n### Legacy requirement\n\n```yaml\nsdd_record: requirement\nid: REQ-other\noperation: add\n```\n"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        read_document(path)
    assert caught.value.code == ("record_position" if case == "mixed_levels" else "acceptance_parent")


def test_flat_legacy_spec_remains_readable(bundle):
    _, change, records, _ = bundle
    assert read_document(change / "specs/feature/spec.md").records == records


@pytest.mark.parametrize("kind", ["requirement", "acceptance"])
def test_spec_rejects_level_four_records(bundle, kind):
    _, change, records, _ = bundle
    path = nested_spec(change, records)
    text = path.read_text(encoding="utf-8")
    heading = "##" if kind == "requirement" else "###"
    text = text.replace(f"{heading} Record\n\n```yaml\nsdd_record: {kind}", f"#### Record\n\n```yaml\nsdd_record: {kind}")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        read_document(path)
    assert caught.value.code == "record_position"


def test_quoted_marker_is_not_silently_ignored(bundle):
    _, change, _, _ = bundle
    path = change / "specs/feature/spec.md"
    path.write_text(path.read_text().replace("sdd_record:", '"sdd_record":'))
    assert len(read_document(path).records) == 2


@pytest.mark.parametrize("replacement", ["extra: true\n", "language: []\n", "document_type: []\n"])
def test_frontmatter_fields(bundle, replacement):
    _, change, _, _ = bundle
    path = change / "proposal.md"
    text = path.read_text()
    if replacement.startswith("extra"):
        text = text.replace("schema_version:", replacement + "schema_version:")
    else:
        key = replacement.split(":")[0]
        text = "\n".join(replacement.strip() if line.startswith(key + ":") else line for line in text.splitlines())
    path.write_text(text)
    with pytest.raises(ValidationError):
        read_document(path)
