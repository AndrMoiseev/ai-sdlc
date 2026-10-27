"""Public route, commit evidence and durable approval contracts."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT.parent
spec = importlib.util.spec_from_file_location("work_basis_loader", COLLECTION / "sdd-spec/scripts/shared.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
paths = loader.load(ROOT, "paths")
documents = loader.load(ROOT, "documents")
snapshots = loader.load(ROOT, "snapshots")
reviews = loader.load(ROOT, "reviews")
BASE = "a" * 40


def document(root, relative, kind, records=(), **extra):
    meta = dict(schema_version=2 if kind in {"state", "review", "decisions"} else 1, work_kind="refactoring", document_type=kind, change_id=root.name, language="en", **extra)
    if kind == "state":
        assert relative == "state.yaml" and not records
        meta.update(flow="plan", next_question=None, checks={"structure": "passed"})
        target = root / relative
        target.write_text(yaml.safe_dump(meta), encoding="utf-8")
        target.with_suffix(".md").write_text("# Continue the approved plan\n", encoding="utf-8")
        return target
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# Document\n"
    for record in records:
        text += "\n### " + record["id"] + "\n\n```yaml\n" + yaml.safe_dump(record, sort_keys=False) + "```\n"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def approved_refactoring(project):
    root = project / "sdd/refactoring/demo"
    local = dict(sdd_record="acceptance", id="AC-local", task="TASK-one", lifetime="persistent",
                 conditions="The candidate is tested", expected="The local contract holds")
    check = dict(id="local", criteria=["AC-local"], test_description="Check local contract",
                 location="tests/contracts.py", run={"command": ["test-runner", "tests/contracts.py"]})
    task = dict(sdd_record="task", id="TASK-one", number=1, scope=[dict(module="core", paths=["src/core"])],
                contributes_to=["AC-result"], preserves=[], preservation_reason="This fixture adds no preserved obligation",
                depends_on=[], status="pending", verification=[check])
    whole = dict(sdd_record="verification", id="CHECK-whole", criteria=["AC-result", "AC-local"],
                 test_description="Check complete scope", location="tests/contracts.py", run=check["run"])
    criterion = dict(sdd_record="criterion", id="AC-result", purpose="result", scope=["Core and consumers"],
                     conditions="The whole transformation is complete", expected="All consumers use the new boundary")
    document(root, "proposal.md", "proposal")
    document(root, "design.md", "design", [criterion])
    document(root, "tasks.md", "tasks", [task, local, whole])
    users = []
    for stage, approval in (("documents", "document_approval"), ("plan", "plan_approval")):
        for kind in (approval, "review_waiver"):
            users.append(dict(sdd_record="user", id="USER-" + stage + "-" + kind.replace("_", "-"),
                              work_kind="refactoring", change_id="demo", kind=kind,
                              scope=dict(stage=reviews.STAGES[stage], **({"lenses": ["plan" if stage == "plan" else "consistency"]} if kind == "review_waiver" else {})),
                              response="Approved synthetic fixture", date="2026-10-24T00:00:00Z", basis_commit=BASE))
    document(root, "review/decisions.md", "decisions", users)
    document(root, "state.yaml", "state", phase="plan_approved", awaiting="none", updated_at="2026-10-24T00:00:00Z",
             document_links=["proposal.md", "design.md", "tasks.md"], review_links=["review/decisions.md"], approval_refs=[u["id"] for u in users])
    document(root, "questions.md", "questions")
    document(root, "review/summary.md", "summary", findings=[])
    return root, users, [task, local, whole]


def invoke(project, script, stage, package="sdd-shared", **options):
    command = ["uv", "run", "--locked", "--script", str(COLLECTION / package / "scripts" / script),
               "--project-root", str(project), "--change", "demo", "--stage", stage,
               "--work-kind", "refactoring"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", shell=False, timeout=90, **options)
    return result, json.loads(result.stdout if script == "check.py" or result.returncode == 0 else result.stderr)


@pytest.mark.parametrize("package", ["sdd-shared", "sdd-spec"])
@pytest.mark.parametrize("stage,names", [("documents", ["design.md", "proposal.md"]), ("plan", ["design.md", "proposal.md", "tasks.md"])])
def test_refactoring_work_basis_public_commands(tmp_path, package, stage, names):
    root, _, _ = approved_refactoring(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result, checked = invoke(tmp_path, "check.py", stage, package)
    assert result.returncode == 0, result.stdout + result.stderr
    assert checked["errors"] == [] and checked["approval_status"]["ready"] is True
    result, diagnostic = invoke(tmp_path, "snapshot.py", stage, package)
    assert result.returncode == 2, result.stderr
    assert diagnostic["code"] == "migration_required"
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert not (root / "specs").exists()


def test_refactoring_work_basis_discovery_retains_both_identities(tmp_path):
    approved_refactoring(tmp_path)
    change = tmp_path / "sdd/changes/demo"
    change.mkdir(parents=True)
    (change / "tasks.md").write_text("ordinary plan")
    assert [(r["work_kind"], r["change_id"], r["has_plan"]) for r in paths.list_work(tmp_path, "demo")] == [
        ("change", "demo", True), ("refactoring", "demo", True)]
    assert paths.change_root(tmp_path, "demo") == change.resolve()


@pytest.mark.parametrize("identity,value", [("work_kind", "change"), ("change_id", "other-work"), ("work_kind", None)])
def test_refactoring_work_basis_copied_authorizations_cannot_transfer(tmp_path, identity, value):
    root, users, _ = approved_refactoring(tmp_path)
    copied = copy.deepcopy(users)
    for user in copied:
        if value is None:
            user.pop(identity)
        else:
            user[identity] = value
    # The same historical commit does not confer authority for another identity.
    assert copied[0]["basis_commit"] == users[0]["basis_commit"]
    document(root, "review/decisions.md", "decisions", copied)
    status = reviews.review_status(tmp_path, root, "plan", "refactoring")
    assert status["errors"] and status["approval_status"]["ready"] is False


@pytest.mark.parametrize("kind", ["state", "questions", "decisions", "review", "summary"])
def test_refactoring_work_basis_ancillary_route_identity(tmp_path, kind):
    root, _, _ = approved_refactoring(tmp_path)
    target = root / "state.yaml" if kind == "state" else document(root, "aux.md", kind)
    def read():
        return documents.read_checkpoint(root, "refactoring") if kind == "state" else documents.read_document(target, "refactoring")
    assert read().meta["work_kind"] == "refactoring"
    target.write_text(target.read_text(encoding="utf-8").replace("change_id: demo", "change_id: other"), encoding="utf-8")
    with pytest.raises(documents.ValidationError, match="change_id"):
        read()


def test_refactoring_work_basis_review_diagnostics_preserve_approval(tmp_path, monkeypatch):
    root, _, _ = approved_refactoring(tmp_path)
    monkeypatch.setattr(reviews, "inspect", lambda *args: {"head": BASE, "status": "accepted"})
    document(root, "review/run/consistency.md", "review", run_id="run", stage="document_review", lens_id="consistency",
             result="completed_no_findings", started_at="2026-10-24T00:00:00Z", finished_at="2026-10-24T00:01:00Z",
             reviewed_commit=BASE, limitations=[])
    result = reviews.review_status(tmp_path, root, "documents", "refactoring")
    assert result["errors"] == [] and result["review_status"]["reports"]["run/consistency"]["evidence"] == "current"
    with (root / "design.md").open("a", encoding="utf-8") as stream:
        stream.write("\nUpdated normative design\n")
    monkeypatch.setattr(reviews, "inspect", lambda *args: {"head": "b" * 40, "status": "accepted"})
    class EvidenceGit:
        def __init__(self, project):
            pass

        def commit_exists(self, oid):
            return oid == BASE
    monkeypatch.setattr(reviews, "Git", EvidenceGit)
    result = reviews.review_status(tmp_path, root, "documents", "refactoring")
    assert result["approval_status"]["ready"] is True
    assert result["review_status"]["reports"]["run/consistency"]["evidence"] == "changed_since_review"


@pytest.mark.parametrize("change", ["../demo", "demo/child", "C:/demo", "demo\\child"])
def test_refactoring_work_basis_rejects_escaping_ids(tmp_path, change):
    with pytest.raises(documents.ValidationError):
        paths.change_root(tmp_path, change, "refactoring")


def test_refactoring_work_basis_rejects_linked_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "sdd").mkdir()
    link = tmp_path / "sdd/refactoring"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, shell=False)
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(outside, target_is_directory=True)
    # The linked directory is inside the project, but outside the declared SDD root.
    # Containment is project-wide: an external target must be rejected.
    external = tmp_path.parent / (tmp_path.name + "-external")
    external.mkdir()
    linked = external / "demo"
    linked.mkdir()
    if os.name == "nt":
        second = outside / "demo"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(second), str(linked)], capture_output=True, shell=False)
        assert result.returncode == 0, result.stderr
    else:
        (outside / "demo").symlink_to(linked, target_is_directory=True)
    with pytest.raises(documents.ValidationError, match="escapes"):
        paths.change_root(tmp_path, "demo", "refactoring")
