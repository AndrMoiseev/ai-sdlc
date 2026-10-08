import pytest
from conftest import write_doc
from lib.validation import validate_documents


def test_documents_need_no_tasks_or_decisions(bundle):
    root, change, _, _ = bundle
    (change / "tasks.md").unlink()
    assert not validate_documents(root, change, "documents")["errors"]


@pytest.mark.parametrize("operation", ["modify", "remove"])
@pytest.mark.parametrize("source_kind", ["specification", "evidence"])
def test_source_contract(bundle, operation, source_kind):
    root, change, records, _ = bundle
    (root / "baseline.md").write_text("### Original behavior\n")
    records[0]["operation"] = operation
    records[0]["source"] = (dict(kind="specification", path="baseline.md", requirement="Original behavior") if source_kind == "specification" else dict(kind="evidence", baseline_missing=True, references=["baseline.md"], observed="Original behavior", assumptions="No additional assumptions"))
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    assert not validate_documents(root, change, "documents")["errors"]
    (root / "baseline.md").unlink()
    assert "missing_path" in {e["code"] for e in validate_documents(root, change, "documents")["errors"]}


def test_missing_criterion_and_bad_decision(bundle):
    root, change, records, _ = bundle
    write_doc(change / "specs/feature/spec.md", "spec", records[:1], capability="feature")
    write_doc(change / "design.md", "design", [dict(sdd_record="decision", id="DEC-design", requirements=[])])
    codes = {e["code"] for e in validate_documents(root, change, "documents")["errors"]}
    assert {"requirement_without_acceptance", "reference_list"} <= codes


def test_missing_requirement_reference(bundle):
    root, change, records, _ = bundle
    records[1]["requirement"] = "REQ-absent"
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    assert "acceptance_requirement" in {e["code"] for e in validate_documents(root, change, "documents")["errors"]}


@pytest.mark.parametrize("source", [None, {}, dict(kind="evidence", baseline_missing=False, references=[], observed="x", assumptions="x"), dict(kind="specification", path="../outside", requirement="x")])
def test_invalid_source(bundle, source):
    root, change, records, _ = bundle
    records[0].update(operation="modify", source=source)
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    assert validate_documents(root, change, "documents")["errors"]


def test_duplicate_id_across_capabilities(bundle):
    root, change, records, _ = bundle
    write_doc(change / "specs/other/spec.md", "spec", records, capability="other")
    assert "duplicate_id" in {e["code"] for e in validate_documents(root, change, "documents")["errors"]}


def test_different_cwd(bundle, tmp_path, monkeypatch):
    root, change, _, _ = bundle
    monkeypatch.chdir(tmp_path)
    assert not validate_documents(root, change, "documents")["errors"]


def test_malformed_evidence_url_returns_diagnostic(bundle):
    import json
    root, change, records, _ = bundle
    records[0].update(operation="modify", source=dict(kind="evidence", baseline_missing=True, references=["https://[bad"], observed="Behavior", assumptions="None"))
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    result = validate_documents(root, change, "documents")
    assert any(e["code"] == "source" and "Invalid evidence URL" in e["message"] for e in result["errors"])
    json.dumps(result)
