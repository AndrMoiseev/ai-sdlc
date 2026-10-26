"""Exercise both v1 document models and reject invalid refactoring plans."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT.parent
spec = importlib.util.spec_from_file_location("refactoring_bootstrap", COLLECTION / "sdd-spec/scripts/shared.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
documents = loader.load(ROOT, "documents", work_kind="refactoring")
validation = loader.load(ROOT, "validation", work_kind="refactoring")


def check(cid, *criteria, run=None):
    return dict(id=cid, criteria=list(criteria), test_description="Check the declared contract",
                location="tests/contracts.py", run=run or {"command": ["pytest", "-q", "tests/contracts.py"]})


def criterion(cid, purpose="result", **extra):
    return dict(sdd_record="criterion", id=cid, purpose=purpose, scope=["Core and consumers"],
                conditions="The declared transformation is complete", expected="The contract holds", **extra)


def acceptance(cid, task, **extra):
    return dict(sdd_record="acceptance", id=cid, task=task, conditions="The task candidate is checked",
                expected="Local contract holds", lifetime=extra.pop("lifetime", "persistent"), **extra)


def task(tid, number, local, dependencies=()):
    return dict(sdd_record="task", id=tid, number=number, scope=[dict(module="core", paths=["src/core", "tests/contracts.py"])],
                contributes_to=["AC-result"], preserves=["AC-preserved"], depends_on=list(dependencies), status="pending",
                verification=[check("local-contract", local), check("api-regression", "AC-preserved")])


def write_document(root, name, records, work_kind="refactoring", **metadata):
    meta = dict(schema_version=1, document_type=name, change_id=root.name, language="en")
    if work_kind is not None:
        meta["work_kind"] = work_kind
    meta.update(metadata)
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# Document\n"
    for record in records:
        text += "\n### " + record["id"] + "\n\n```yaml\n" + yaml.safe_dump(record, sort_keys=False) + "```\n"
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def plan(tmp_path):
    root = tmp_path / "sdd/refactoring/sample-work"
    baseline = tmp_path / "docs/baseline.md"
    baseline.parent.mkdir()
    baseline.write_text("# Contract\n\n### Old boundary\n\n```yaml\nsdd_record: decision\nid: DEC-old-boundary\n```\n", encoding="utf-8")
    design = [criterion("AC-result"), criterion("AC-result-part", parent="AC-result"),
              criterion("AC-preserved", "preservation", source=dict(kind="specification", path="docs/baseline.md", requirement="Contract")),
              dict(sdd_record="decision", id="DEC-new-boundary", criteria=["AC-result", "AC-preserved"],
                   supersedes=[dict(path="docs/baseline.md", id="DEC-old-boundary")])]
    tasks = [task("TASK-introduce", 1, "AC-adapter"),
             acceptance("AC-adapter", "TASK-introduce", lifetime="transitional", until_task="TASK-remove", replaced_by=["AC-converted"]),
             task("TASK-convert", 2, "AC-converted", ["TASK-introduce"]),
             acceptance("AC-converted", "TASK-convert"),
             task("TASK-remove", 3, "AC-clean", ["TASK-convert"]), acceptance("AC-clean", "TASK-remove"),
             dict(sdd_record="verification", id="CHECK-whole", **{key: value for key, value in check("whole", "AC-result", "AC-result-part", "AC-preserved", "AC-converted", "AC-clean").items() if key != "id"})]
    tasks[2]["contributes_to"].append("AC-result-part")
    tasks[4]["test_changes"] = [dict(id="retire-adapter", action="remove", group="Adapter boundary in tests/adapter",
                                      criteria=["AC-adapter"], reason="New boundary replaces the adapter", decision="DEC-new-boundary", replacement_criteria=[])]
    write_document(root, "proposal", [])
    return dict(project=tmp_path, root=root, design=design, tasks=tasks)


def validate(plan, stage="plan"):
    write_document(plan["root"], "design", plan["design"])
    write_document(plan["root"], "tasks", plan["tasks"])
    return validation.validate_documents(plan["project"], plan["root"], stage, work_kind="refactoring")


def codes(plan, stage="plan"):
    return {error["code"] for error in validate(plan, stage)["errors"]}


def test_refactoring_documents_complete_model_without_specs(plan):
    result = validate(plan)
    assert result["errors"] == []
    assert result["warnings"] == []
    assert result["progress"] == {"done": 0, "total": 3}
    assert result["tasks"]["available_by_graph"] == ["TASK-introduce"]
    assert not (plan["root"] / "specs").exists()


def test_refactoring_documents_documents_stage_does_not_require_tasks(plan):
    write_document(plan["root"], "design", plan["design"])
    assert validation.validate_documents(plan["project"], plan["root"], "documents", "refactoring") == {"errors": [], "warnings": []}


def test_refactoring_documents_shared_versions_keep_change_covers_and_unique_owners(tmp_path, plan):
    assert validate(plan)["errors"] == []
    root = tmp_path / "sdd/changes/sample-change"
    for name, relative in [("proposal", "proposal.md"), ("design", "design.md"), ("spec", "specs/sample-capability/spec.md"), ("tasks", "tasks.md")]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((COLLECTION / "sdd-spec/templates" / f"{name}.md").read_bytes())
    original = {path: path.read_bytes() for path in root.rglob("*.md")}
    assert validation.validate_documents(tmp_path, root, "plan")["errors"] == []
    task_path = root / "tasks.md"
    document = documents.read_document(task_path)
    assert "covers" in document.records[0] and "contributes_to" not in document.records[0]
    duplicated = copy.deepcopy(document.records[0])
    duplicated.update(id="TASK-duplicate", number=2)
    write_document(root, "tasks", [document.records[0], duplicated], work_kind=None)
    assert "task_coverage" in {error["code"] for error in validation.validate_documents(tmp_path, root, "plan")["errors"]}
    assert all(path.read_bytes() == content for path, content in original.items() if path != task_path)


@pytest.mark.parametrize("context,declared,version,error", [
    ("change", "refactoring", 1, "work_kind_mismatch"),
    ("refactoring", None, 1, "work_kind_mismatch"),
    ("refactoring", "change", 1, "work_kind_mismatch"),
    ("unknown", "refactoring", 1, "unsupported_work_kind"),
    ("refactoring", "unknown", 1, "unsupported_work_kind"),
    ("refactoring", "refactoring", 2, "unsupported_version"),
    ("refactoring", "refactoring", True, "unsupported_version"),
    ("refactoring", "refactoring", "1", "unsupported_version"),
])
def test_refactoring_documents_schema_dispatch_errors_preserve_bytes(tmp_path, context, declared, version, error):
    root = tmp_path / "standalone"
    path = write_document(root, "proposal", [], work_kind=declared, schema_version=version)
    before = path.read_bytes()
    with pytest.raises(documents.ValidationError) as exc:
        documents.read_document(path, work_kind=context)
    assert exc.value.code == error
    assert exc.value.path == str(path)
    assert path.read_bytes() == before


def test_refactoring_documents_reject_wrong_root_and_spec_type(tmp_path):
    root = tmp_path / "sdd/changes/sample-work"
    path = write_document(root, "proposal", [])
    with pytest.raises(documents.ValidationError) as exc:
        documents.read_document(path, "refactoring")
    assert exc.value.code == "work_kind_mismatch"
    with pytest.raises(documents.ValidationError) as exc:
        validation.validate_documents(tmp_path, root, "documents", "refactoring")
    assert exc.value.code == "work_kind_mismatch"
    path = write_document(tmp_path / "standalone", "spec", [], capability="core")
    with pytest.raises(documents.ValidationError) as exc:
        documents.read_document(path, "refactoring")
    assert exc.value.code == "document_type"


@pytest.mark.parametrize("field", ["scope", "contributes_to", "preserves", "verification"])
def test_refactoring_documents_missing_required_task_field(plan, field):
    del plan["tasks"][0][field]
    assert "record_fields" in codes(plan)


@pytest.mark.parametrize("mutation,error", [
    (lambda p: p["tasks"][1].update(expected=""), "record_text"),
    (lambda p: p["tasks"].pop(1), "local_acceptance"),
    (lambda p: p["tasks"][1].update(task="TASK-missing"), "acceptance_task"),
    (lambda p: p["tasks"][1].update(id="AC-result"), "duplicate_id"),
    (lambda p: p["tasks"][0].update(covers=["AC-result"]), "record_fields"),
    (lambda p: p["tasks"][0].update(scope=[]), "task_scope"),
    (lambda p: p["tasks"][0].update(scope=[{"module": "core", "paths": ["../escape"]}]), "path_escape"),
    (lambda p: p["tasks"][0].update(scope=[{"module": "core", "paths": ["C:/escape"]}]), "path_escape"),
    (lambda p: p["tasks"][0].update(contributes_to=["DEC-new-boundary"]), "missing_reference"),
    (lambda p: p["tasks"][0].update(preserves=["AC-result"]), "missing_reference"),
    (lambda p: p["tasks"][0].update(preserves=[]), "preservation_reason"),
    (lambda p: p["tasks"][2].update(contributes_to=["AC-result"]), "contribution_coverage"),
    (lambda p: p["tasks"][0].update(depends_on=["TASK-missing"]), "missing_reference"),
    (lambda p: p["tasks"][0].update(depends_on=["TASK-introduce"]), "self_reference"),
    (lambda p: p["tasks"][0].update(depends_on=["TASK-remove"]), "task_cycle"),
    (lambda p: p["tasks"][0].update(number=True), "task_numbers"),
    (lambda p: p["tasks"][0].update(status="accepted"), "task_status"),
    (lambda p: p["tasks"][0]["verification"][0].update(criteria=["AC-result"]), "missing_reference"),
    (lambda p: p["tasks"][0]["verification"].pop(0), "verification_coverage"),
    (lambda p: p["tasks"][0]["verification"][0].update(id="api-regression"), "verification_id"),
    (lambda p: p["tasks"][0]["verification"][0].update(run={"command": "pytest -q"}), "verification_run"),
    (lambda p: p["tasks"][0]["verification"][0].update(run={"command": ["", "-q"]}), "verification_run"),
    (lambda p: p["tasks"][0]["verification"][0].update(run={"command": ["pytest", "\0"]}), "verification_run"),
    (lambda p: p["tasks"][0]["verification"][0].update(run={"procedure": "../escape.md"}), "path_escape"),
    (lambda p: p["tasks"][0]["verification"][0].update(location="tests/test.py::test_case"), "path_escape"),
    (lambda p: p["tasks"][-1].update(criteria=["AC-result"]), "whole_coverage"),
    (lambda p: p["tasks"].pop(), "whole_verification"),
    (lambda p: p["tasks"][-1].update(run={"setup_required": "Create a whole-work check"}), "setup_task"),
    (lambda p: p["tasks"][-1].update(setup_task="TASK-missing"), "setup_task"),
    (lambda p: p["tasks"][-1].update(criteria=["AC-adapter"]), "missing_reference"),
])
def test_refactoring_documents_invalid_plans(plan, mutation, error):
    mutation(plan)
    assert error in codes(plan)


@pytest.mark.parametrize("mutation,error", [
    (lambda p: p["design"][0].update(scope=[]), "criterion_scope"),
    (lambda p: p["design"][0].update(parent="AC-result"), "self_reference"),
    (lambda p: p["design"][0].update(parent="AC-result-part"), "parent_cycle"),
    (lambda p: p["design"][0].update(parent="AC-preserved"), "criterion_parent"),
    (lambda p: p["design"][2].update(parent="AC-result"), "criterion_parent"),
    (lambda p: p["design"][2].pop("source"), "source"),
    (lambda p: p["design"][2]["source"].update(path="docs/missing.md"), "missing_path"),
    (lambda p: p["design"][2]["source"].update(requirement="REQ-missing"), "source_requirement"),
    (lambda p: p["design"][3].update(requirements=["REQ-artificial"]), "record_fields"),
    (lambda p: p["design"][3].update(criteria=["DEC-new-boundary"]), "missing_reference"),
    (lambda p: p["design"][3]["supersedes"][0].update(id="DEC-missing"), "supersedes"),
    (lambda p: p["design"][3]["supersedes"][0].update(path="../escape.md"), "path_escape"),
])
def test_refactoring_documents_invalid_design(plan, mutation, error):
    mutation(plan)
    assert error in codes(plan, "documents")


@pytest.mark.parametrize("mutation,error", [
    (lambda p: p["tasks"][1].pop("until_task"), "acceptance_transition"),
    (lambda p: p["tasks"][1].update(replaced_by=[]), "reference_list"),
    (lambda p: p["tasks"][1].update(until_task="TASK-introduce"), "until_task_reachability"),
    (lambda p: p["tasks"][1].update(until_task="TASK-missing"), "until_task"),
    (lambda p: p["tasks"][4].update(depends_on=[]), "until_task_reachability"),
    (lambda p: p["tasks"][1].update(replaced_by=["AC-result"]), "replacement_verification"),
    (lambda p: p["tasks"][1].update(replaced_by=["DEC-new-boundary"]), "missing_reference"),
    (lambda p: p["tasks"][1].update(replaced_by=["AC-adapter"]), "self_reference"),
    (lambda p: p["tasks"][3].update(lifetime="transitional", until_task="TASK-remove", replaced_by=["AC-adapter"]), "replacement_cycle"),
    (lambda p: p["tasks"][3].update(until_task="TASK-remove"), "acceptance_transition"),
    (lambda p: p["design"][2].update(until_task="TASK-remove"), "record_fields"),
])
def test_refactoring_documents_invalid_transitions(plan, mutation, error):
    mutation(plan)
    assert error in codes(plan)


def test_refactoring_documents_until_task_own_replacement_and_predecessor_rechecks(plan):
    assert validate(plan)["errors"] == []
    plan["tasks"][1]["replaced_by"] = ["AC-clean"]
    assert validate(plan)["errors"] == []
    plan["tasks"][4]["verification"].append(check("foreign-local", "AC-converted"))
    assert "missing_reference" in codes(plan)


def test_refactoring_documents_setup_procedure_empty_preserves_and_symmetry(plan):
    plan["tasks"][-1].update(run={"setup_required": "Create the final check"}, setup_task="TASK-convert")
    plan["tasks"][0]["verification"][0]["run"] = {"procedure": "docs/baseline.md#contract"}
    plan["tasks"][0]["verification"][1]["run"] = {"setup_required": "Prepare regression check"}
    plan["tasks"][2].update(preserves=[], preservation_reason="This isolated step has no applicable preservation area")
    plan["tasks"][2]["verification"].pop(1)
    plan["tasks"][0]["cannot_parallel_with"] = ["TASK-remove"]
    result = validate(plan)
    assert result["errors"] == []
    assert result["tasks"]["cannot_parallel_with"]["TASK-remove"] == ["TASK-introduce"]


def test_refactoring_documents_evidence_and_supersedes_heading(plan):
    plan["design"][2]["source"] = dict(kind="evidence", baseline_missing=True, references=["docs/baseline.md", "https://example.test/evidence"], observed="Existing calls preserve contracts", assumptions="Only listed routes were observed")
    plan["design"][3]["supersedes"] = [dict(path="docs/baseline.md", anchor="old-boundary")]
    assert validate(plan)["errors"] == []
    plan["design"][2]["source"]["baseline_missing"] = False
    assert "source" in codes(plan)


def test_refactoring_documents_removed_preservation_needs_replacement(plan):
    change = plan["tasks"][4]["test_changes"][0]
    change["criteria"] = ["AC-preserved"]
    assert "test_change_preservation" in codes(plan)
    change["replacement_criteria"] = ["AC-preserved"]
    assert validate(plan)["errors"] == []
    change.pop("decision")
    change["replacement_criteria"] = []
    assert "test_change_basis" in codes(plan)


def test_refactoring_documents_relocated_loader_support_and_no_legacy_fallback(tmp_path):
    collection = tmp_path / "relocated"
    shutil.copytree(ROOT, collection / "sdd-shared")
    target = collection / "sdd-shared"
    assert loader.locate(explicit=target, work_kind="refactoring") == target.resolve()
    assert loader.load(target, "documents", work_kind="refactoring").WORK_KINDS == {"change", "refactoring"}
    (target / "api.json").write_text('{"api_version": 1}', encoding="utf-8")
    assert loader.locate(explicit=target) == target.resolve()
    with pytest.raises(ValueError, match="does not support refactoring"):
        loader.locate(explicit=target, work_kind="refactoring")
    (target / "api.json").write_bytes((ROOT / "api.json").read_bytes())
    (target / "scripts/sdd_shared/refactoring.py").unlink()
    with pytest.raises(ValueError, match="Incomplete sdd-shared"):
        loader.locate(explicit=target, work_kind="refactoring")


def test_refactoring_documents_schema_resource_matches_record_vocabulary():
    schema = json.loads((ROOT / "schemas/refactoring.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$defs"]["metadata"]["properties"]["schema_version"] == {"const": 1}
    assert schema["$defs"]["metadata"]["properties"]["work_kind"] == {"const": "refactoring"}
    assert {"criterion", "decision", "task", "acceptance", "verification"} <= schema["$defs"].keys()
    vocabulary = documents.document_schema({"schema_version": 1, "work_kind": "refactoring"}, "refactoring")[0]
    for kind, (required, optional, _) in vocabulary.items():
        definition = schema["$defs"][kind]
        assert set(definition["required"]) == required | {"sdd_record", "id"}
        assert set(definition["properties"]) == required | optional | {"sdd_record", "id"}
        assert definition["additionalProperties"] is False


@pytest.mark.parametrize("field,value,error", [
    ("verification", [None], "verification"),
    ("verification", [], "verification"),
    ("contributes_to", [None], "reference_list"),
    ("depends_on", ["TASK-convert", "TASK-convert"], "duplicate_reference"),
    ("preserves", {}, "reference_list"),
    ("scope", [{"module": "core", "paths": []}], "task_scope"),
    ("scope", [{"module": ""}], "task_scope"),
    ("test_changes", [None], "test_changes"),
])
def test_refactoring_documents_malformed_values_are_diagnostics(plan, field, value, error):
    plan["tasks"][0][field] = value
    assert error in codes(plan)


def test_refactoring_documents_unknown_fields_and_nested_examples(tmp_path):
    path = write_document(tmp_path / "standalone", "design", [])
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n````text\n### Example\n\n```yaml\nsdd_record: requirement\nid: REQ-illustration\n```\n````\n")
    assert documents.read_document(path, "refactoring").records == []
    write_document(path.parent, "design", [dict(sdd_record="criterion", id="AC-test", purpose="result", conditions="When", expected="Then", scope=["core"], invented=True)])
    with pytest.raises(documents.ValidationError) as exc:
        documents.read_document(path, "refactoring")
    assert exc.value.code == "record_fields"
