from pathlib import Path
import yaml
from lib.reviews import review_status
from lib.snapshots import snapshot
import pytest
from lib.documents import InputError


def write(path, meta, records=()):
    meta = {"document_type": path.stem, **meta}
    class NoAliases(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "---\n" + yaml.dump(meta, Dumper=NoAliases, sort_keys=False) + "---\n"
    for record in records:
        body += "\n### Record\n\n```yaml\n" + yaml.safe_dump(record, sort_keys=False) + "```\n"
    path.write_text(body, encoding="utf-8")


def project(tmp_path):
    root = tmp_path / "sdd/changes/demo"
    for name in ["proposal.md", "design.md", "specs/example/spec.md", "tasks.md"]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"normative\n")
    return root


def finding():
    return dict(sdd_record="finding", id="FIND-example", source="spec", target={"path": "design.md"}, severity="recommendation", problem="Gap", impact="Risk", suggestion="Fix")


def report(tmp_path, root, run="run-one", lens="consistency", records=(), result=None, after=None, stage="documents"):
    inputs = snapshot(tmp_path, "demo", stage)
    meta = dict(schema_version=1, document_type="review", change_id="demo", language="en", run_id=run, stage="document_review" if stage == "documents" else "plan_review", lens_id=lens, result=result or ("completed_with_findings" if records else "completed_no_findings"), started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:01:00Z", inputs=inputs, inputs_after=inputs if after is None else after, freshness="current", limitations=[])
    write(root / f"review/{run}/{lens}.md", meta, records)
    return meta


def test_local_ids_and_immutable_history(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding()])
    report(tmp_path, root, run="run-two", records=[finding()])
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert len(result["review_status"]["unresolved_findings"]) == 2
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_duplicate_findings_and_result_contract(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding(), finding()])
    assert review_status(tmp_path, root, "documents")["errors"]
    report(tmp_path, root, records=[finding()], result="completed_no_findings")
    assert review_status(tmp_path, root, "documents")["errors"]


def test_incomplete_and_freshness_independent(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, result="incomplete")
    result = review_status(tmp_path, root, "documents")["review_status"]
    assert result["coverage"]["consistency"] == "incomplete"
    assert result["reports"]["run-one/consistency"]["freshness"] == "current"
    (root / "design.md").write_text("changed")
    assert review_status(tmp_path, root, "documents")["review_status"]["coverage"]["consistency"] == "stale"


def test_summary_requires_full_resolvable_keys(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding()])
    write(root / "review/summary.md", {"schema_version": 1, "findings": [{"finding": "FIND-example", "related_to": [], "duplicates": []}]})
    assert review_status(tmp_path, root, "documents")["errors"]


@pytest.mark.parametrize("field,value", [("stage", []), ("run_id", []), ("limitations", 3), ("inputs", {}), ("lens_id", None), ("extra", True)])
def test_bad_report_shapes_are_diagnostics(tmp_path, field, value):
    root = project(tmp_path)
    meta = report(tmp_path, root)
    meta[field] = value
    write(root / "review/run-one/consistency.md", meta)
    assert review_status(tmp_path, root, "documents")["errors"]


def test_unsupported_report_version_cannot_be_swallowed(tmp_path):
    root = project(tmp_path)
    meta = report(tmp_path, root)
    meta["schema_version"] = 2
    write(root / "review/run-one/consistency.md", meta)
    with pytest.raises(InputError):
        review_status(tmp_path, root, "documents")


def test_common_change_invalidates_all_lenses(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root)
    report(tmp_path, root, lens="security")
    (root / "design.md").write_text("new")
    result = review_status(tmp_path, root, "documents")
    assert all(r["freshness"] == "stale" for r in result["review_status"]["reports"].values())
