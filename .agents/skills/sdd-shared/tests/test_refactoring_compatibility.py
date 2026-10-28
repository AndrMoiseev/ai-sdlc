"""Ordinary-work contracts across the complete updated SDD bundle.

Saved-state migration covers parallel runs from the user-selected 0529577 schema-2 runtime.
The portable fixture below transcribes that format independently of current
initialize/seal/history helpers; it is not a captured historical execution.
Its provenance is source inspection, not a claim of pre-v2 resume support.
No test needs repository history or the author's historical checkout.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from test_contract import COLLECTION, bootstrap, install, inventory


BASELINE_SOURCE = {
    "commit": "05295779d12f45aee90ab2e1dde574697ad3ed9b",
    "state.py": "59d2f469eb1dc370d995834e0f7e9d1461b77e5f",
    "state_history.py": "509f360b1c3b270d4feaab93cbc5bd014d157a5d",
    "state_objects.py": "928b5c9c35ed8822d7d85c116bd06599aef16749",
}
STAMP = "2026-10-08T00:00:00Z"
INSTRUCTION = {"text": "Implement synthetic fixture", "source": "synthetic-test-user"}
BASE = "a" * 40


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def write_document(root, relative, kind, records=(), **extra):
    meta = dict(schema_version=2 if kind in {"state", "review", "decisions"} else 1,
                change_id="demo", language="en", document_type=kind, **extra)
    if meta["schema_version"] == 2:
        meta["work_kind"] = "change"
    if kind == "state":
        assert relative == "state.yaml" and not records
        meta.update(flow="plan", next_question=None, checks={"structure": "passed"})
        (root / relative).write_text(yaml.safe_dump(meta), encoding="utf-8")
        (root / "state.md").write_text("# Continue the approved plan\n", encoding="utf-8")
        return
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# Synthetic legacy fixture\n"
    for record in records:
        text += "\n### Record\n\n```yaml\n" + yaml.safe_dump(record, sort_keys=False) + "```\n"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def manifest(root, stage):
    names = ["design.md", "proposal.md", "specs/demo/spec.md"]
    if stage == "plan":
        names.append("tasks.md")
    return [{"path": name, "sha256": digest((root / name).read_bytes())} for name in sorted(names)]


@pytest.fixture
def ordinary(tmp_path):
    """Fixed pre-route document contract; never copy evolving templates."""
    project = tmp_path / "ordinary project"
    root = project / "sdd/changes/demo"
    task = dict(sdd_record="task", id="TASK-one", number=1, covers=["AC-one"],
                depends_on=[], status="pending", verification=[dict(
                    criteria=["AC-one"], test_description="Verify fixture result",
                    location="check.py", run={"command": ["python", "-B", "check.py"]})])
    for kind in ("proposal", "design", "tasks"):
        write_document(root, kind + ".md", kind, [task] if kind == "tasks" else [])
    write_document(root, "specs/demo/spec.md", "spec", [
        dict(sdd_record="requirement", id="REQ-one", operation="add"),
        dict(sdd_record="acceptance", id="AC-one", requirement="REQ-one",
             conditions="Numbers are added", expected="The sum is preserved"),
    ], capability="demo")
    users = []
    for stage, approval in (("documents", "document_approval"), ("plan", "plan_approval")):
        for kind in (approval, "review_waiver"):
            scope = {"stage": "document_review" if stage == "documents" else "plan_review"}
            if kind == "review_waiver":
                scope["lenses"] = ["consistency" if stage == "documents" else "plan"]
            users.append(dict(sdd_record="user", id="USER-" + stage + "-" + kind.replace("_", "-"),
                              work_kind="change", change_id="demo", kind=kind, scope=scope,
                              response="Synthetic test approval only", date=STAMP, basis_commit=BASE))
    write_document(root, "review/decisions.md", "decisions", users)
    write_document(root, "state.yaml", "state", phase="plan_approved", awaiting="none",
                   updated_at=STAMP, document_links=["tasks.md"],
                   review_links=["review/decisions.md"], approval_refs=[u["id"] for u in users])
    (project / "check.py").write_bytes(b"assert 2 + 3 == 5\n")
    return project, root, task, users


def run(command, cwd):
    return subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", timeout=120, shell=False)


def cli(collection, package, script, cwd, *args):
    return run(["uv", "run", "--quiet", "--python", sys.executable, "--locked", "--script",
                collection / package / "scripts" / script, *args], cwd)


def request(collection, workspace, operation, **args):
    path = workspace / "request.json"
    path.write_bytes(encoded({"operation": operation, "args": args}))
    return cli(collection, "sdd-apply", "execute.py", workspace, "--request", path)


@pytest.fixture(params=["source", "relocated"])
def collection(request, tmp_path):
    return COLLECTION if request.param == "source" else install(tmp_path, ("sdd-spec", "sdd-apply"))


def test_refactoring_compatibility_default_apis_preserve_bytes_and_approvals(ordinary):
    project, root, task, users = ordinary
    before = inventory(root)
    loader = bootstrap()
    shared = COLLECTION / "sdd-shared"
    documents = loader.load(shared, "documents")
    snapshots = loader.load(shared, "snapshots")
    reviews = loader.load(shared, "reviews")
    validation = loader.load(shared, "validation")

    for stage in ("documents", "plan"):
        with pytest.raises(documents.InputError, match="Byte manifests are retired"):
            snapshots.snapshot(project, "demo", stage)
        assert validation.validate_documents(project, root, stage)["errors"] == []
        approval = reviews.review_status(project, root, stage)["approval_status"]
        assert approval["approved"] is True and approval["ready"] is True
        for user in users:
            if user["scope"]["stage"] == reviews.STAGES[stage]:
                assert approval["applicability"][user["id"]] is True
    assert documents.read_document(root / "tasks.md").records == [task]
    assert "work_kind" not in documents.read_document(root / "tasks.md").meta
    assert documents.read_document(root / "review/decisions.md").records == users
    assert inventory(root) == before
    assert not (project / "sdd/refactoring").exists()


@pytest.mark.parametrize("changed,stages", [
    ("design.md", ("documents", "plan")), ("tasks.md", ("plan",)),
])
def test_refactoring_compatibility_approval_survives_normative_edits(ordinary, changed, stages):
    project, root, _, _ = ordinary
    before = inventory(root)
    reviews = bootstrap().load(COLLECTION / "sdd-shared", "reviews")
    (root / changed).write_bytes(before[Path(changed)] + b"\nChanged normative fixture.\n")
    changed_bytes = inventory(root)

    for stage in stages:
        approval = reviews.review_status(project, root, stage)["approval_status"]
        assert approval["approved"] is True and approval["ready"] is True
    assert inventory(root) == changed_bytes
    (root / changed).write_bytes(before[Path(changed)])
    for stage in stages:
        assert reviews.review_status(project, root, stage)["approval_status"]["ready"] is True
    assert inventory(root) == before


def test_refactoring_compatibility_covers_keeps_one_owner(ordinary):
    project, root, task, _ = ordinary
    validation = bootstrap().load(COLLECTION / "sdd-shared", "validation")
    duplicate = deepcopy(task)
    duplicate.update(id="TASK-other", number=2)
    write_document(root, "tasks.md", "tasks", [task, duplicate])
    before = inventory(root)

    result = validation.validate_documents(project, root, "plan")

    assert "task_coverage" in {error["code"] for error in result["errors"]}
    assert inventory(root) == before
    write_document(root, "tasks.md", "tasks", [task])
    assert validation.validate_documents(project, root, "plan")["errors"] == []


def git_project(project):
    for args in (("init", "--initial-branch=fixture"),
                 ("config", "user.name", "Synthetic fixture"),
                 ("config", "user.email", "fixture@example.invalid"),
                 ("config", "core.autocrlf", "false"),
                 ("add", "."), ("commit", "-m", "Synthetic ordinary fixture")):
        result = run(["git", *args], project)
        assert result.returncode == 0, result.stdout + result.stderr
    result = run(["git", "rev-parse", "HEAD"], project)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def put_object(directory, value):
    """Frozen wire-format writer, independent of the implementation under test."""
    raw = encoded(value)
    sha = digest(raw)
    relative = f"objects/{sha[:2]}/{sha}.json"
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": relative, "sha256": sha, "bytes": len(raw), "kind": "object"}


def saved_execution(ordinary, collection):
    project, root, plan, _ = ordinary
    head = git_project(project)
    directory = root / "execution"
    directory.mkdir()
    basis = dict(schema_version=1, project_root=str(project.resolve()), change_id="demo",
                 change_root=str(root.resolve()), instruction=INSTRUCTION,
                 sdd_spec=str((collection / "sdd-spec").resolve()), checks={},
                 manifest=manifest(root, "plan"), tasks=[plan], branch="fixture", head=head)
    task = dict(plan=plan, status="pending", attempt=0, candidate=None, evidence=[], reviews=[],
                commits=[], blockers=[], review_limit=3, review_rounds_started=0,
                review_rounds_completed=0, active_review=None, test_repair_limit=5,
                test_repair_cycles_started=0, active_repair=None, repair_cycles=[],
                budget_decisions=[], checks=[], worktree=None, roles=[], paths=[])
    state = dict(schema_version=2, change_id="demo", run_id="legacy-fixture", revision=1,
                 status="active", owner="synthetic-owner", basis=basis, mode="parallel",
                 parallel_request=deepcopy(INSTRUCTION), tasks={"TASK-one": task}, roles={},
                 blockers=[], updated_at=STAMP, final=None)
    # One existing resume proves preservation of a nonempty chain and its index.
    event = dict(event_id="saved-resume", run_id=state["run_id"], expected_revision=0,
                 owner=state["owner"], type="resume", task_id=None,
                 payload={"host_trace": "synthetic saved fixture", "live_contexts": []})
    result = dict(status="active", issues=[], preserved_roles={}, stale_worktrees=[])
    entry = dict(event_id=event["event_id"], fingerprint=digest(event), event=event,
                 revision=1, previous=None, result=result, time=STAMP)
    state["event_head"] = put_object(directory, entry)
    state["event_index"] = put_object(directory, {"event_id": event["event_id"],
                                                "entry": state["event_head"]})
    files = {(Path("sdd/changes/demo") / path).as_posix(): {"sha256": digest(raw)}
             for path, raw in inventory(root).items() if path.parts[0] != "execution"}
    state["baseline"] = {"$object": put_object(directory, dict(
        files=files, digest=digest(files), commit=head, branch="fixture", dirty_paths=[]))}
    state["integrity"] = digest(state)
    (directory / "state.json").write_bytes(encoded(state))
    return directory, state


def test_refactoring_compatibility_saved_state_requires_explicit_migration(ordinary, collection, tmp_path):
    _, root, _, _ = ordinary
    directory, saved = saved_execution(ordinary, collection)
    before = inventory(root)
    packages = {name: inventory(collection / name) for name in ("sdd-shared", "sdd-spec", "sdd-apply")}
    event = dict(event_id="updated-resume", run_id=saved["run_id"], expected_revision=1,
                 owner=saved["owner"], type="resume", task_id=None,
                 payload={"host_trace": "synthetic current fixture", "live_contexts": []})
    for operation, arguments in (("read", {"view": "full"}), ("audit", {}), ("event", {"event": event})):
        result = request(collection, tmp_path, operation, directory=str(directory), **arguments)
        assert result.returncode == 1, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["ok"] is False and report["code"] == "state_version"
        assert "migration" in report["message"]
        assert inventory(root) == before
    assert {name: inventory(collection / name) for name in packages} == packages

def test_refactoring_compatibility_unsupported_v1_is_not_rewritten(ordinary, tmp_path):
    directory, state = saved_execution(ordinary, COLLECTION)
    # This is explicitly an unsupported-format negative case, not migration.
    state.update(schema_version=1, revision=0, events=[])
    state.pop("event_head")
    state.pop("event_index")
    state.pop("integrity")
    state["integrity"] = digest(state)
    (directory / "state.json").write_bytes(encoded(state))
    before = inventory(directory)

    result = request(COLLECTION, tmp_path, "read", directory=str(directory), view="full")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False and report["code"] == "state_version"
    assert inventory(directory) == before
