"""Validate filled refactoring templates using the real public check command."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

SKILL = Path(__file__).resolve().parents[1]


def project(tmp_path):
    change = tmp_path / "sdd/refactoring/sample-refactoring"
    change.mkdir(parents=True)
    for kind in ("proposal", "design", "tasks"):
        (change / f"{kind}.md").write_bytes((SKILL / f"templates/refactoring-{kind}.md").read_bytes())
    contracts = tmp_path / "docs/contracts.md"
    contracts.parent.mkdir()
    contracts.write_text("### API\n\n```yaml\nsdd_record: requirement\nid: REQ-product-api\noperation: add\n```\n", encoding="utf-8")
    return change


def check(root, stage="plan"):
    result = subprocess.run([sys.executable, "-B", str(SKILL / "scripts/check.py"),
                             "--project-root", str(root), "--change", "sample-refactoring",
                             "--work-kind", "refactoring", "--stage", stage],
                            capture_output=True, text=True, encoding="utf-8", shell=False)
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("stage", ["documents", "plan"])
def test_refactoring_templates_accept_multiple_contributors_without_specs(tmp_path, stage):
    change = project(tmp_path)
    if stage == "documents":
        (change / "tasks.md").unlink()
    result, output = check(tmp_path, stage)
    assert result.returncode == 0, result.stdout + result.stderr
    assert output["errors"] == []
    assert not (change / "specs").exists()


@pytest.mark.parametrize("before,after,element", [
    ('"AC-product-id"', '"AC-missing"', "AC-missing"),
    ('"task": "TASK-core"', '"task": "TASK-orders"', "TASK-core"),
    ('"depends_on": []', '"depends_on": ["TASK-orders"]', "TASK-core"),
])
def test_refactoring_templates_diagnose_invalid_plan_with_ids(tmp_path, before, after, element):
    change = project(tmp_path)
    path = change / "tasks.md"
    original = path.read_text(encoding="utf-8")
    assert before in original
    path.write_text(original.replace(before, after), encoding="utf-8")
    result, output = check(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert output["errors"]
    assert element in json.dumps(output["errors"], ensure_ascii=False)
    assert all({"code", "path", "element_id", "message"} <= error.keys() for error in output["errors"])


def test_refactoring_templates_diagnose_uncovered_design_criterion(tmp_path):
    change = project(tmp_path)
    path = change / "design.md"
    path.write_text(path.read_text(encoding="utf-8") + '\n### Uncovered\n\n```yaml\nsdd_record: criterion\nid: AC-uncovered\npurpose: result\nscope: [shipping]\nconditions: Completed migration\nexpected: Shipping uses ProductId\n```\n', encoding="utf-8")
    result, output = check(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "AC-uncovered" in json.dumps(output["errors"])


def test_refactoring_templates_accept_explicit_baseline_gap(tmp_path):
    change = project(tmp_path)
    path = change / "design.md"
    text = path.read_text(encoding="utf-8")
    old_source = '"kind": "specification",\n    "path": "docs/contracts.md",\n    "requirement": "REQ-product-api"'
    evidence = {"kind": "evidence", "baseline_missing": True, "references": ["docs/contracts.md"],
                "observed": "Current API signatures are available; historical errors have no behavioral tests.",
                "assumptions": "Equivalence is unproven; obtain characterization evidence before transformation."}
    assert old_source in text
    path.write_text(text.replace(old_source, json.dumps(evidence)[1:-1]), encoding="utf-8")
    result, output = check(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert output["errors"] == []