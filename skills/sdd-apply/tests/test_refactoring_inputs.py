"""Initialize and read both actual approved bundles through public dispatch."""
from lib.repository import repository

import copy
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from lib.api import dispatch
from lib.common import Rejected
from lib.state import initialize, snapshot, read

COLLECTION = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("refactoring_bundle_fixture", COLLECTION / "sdd-shared/tests/test_refactoring_work_basis.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
INSTRUCTION = {"text": "Execute the approved fixture plan", "source": "synthetic-user-message"}


def arguments(project, work_kind="refactoring"):
    return dict(project_root=str(project), change="demo", instruction=INSTRUCTION,
                sdd_shared=str(COLLECTION / "sdd-shared"), work_kind=work_kind)


@pytest.mark.parametrize("work_kind", ["change", "refactoring"])
def test_refactoring_inputs_public_initialize_read_and_dashboard(project, work_kind):
    refactoring, _, records = fixtures.approved_refactoring(project)
    args = arguments(project, work_kind)
    basis = dispatch({"operation": "validate", "args": args})
    expected_root = refactoring if work_kind == "refactoring" else project / "sdd/changes/demo"
    assert basis["work_kind"] == work_kind and Path(basis["change_root"]) == expected_root
    assert [r["id"] for r in basis["tasks"]] == ["TASK-one"]
    assert all(r["sdd_record"] == "task" for r in basis["tasks"])
    if work_kind == "refactoring":
        assert basis["acceptance"] == [records[1]] and basis["verification"] == [records[2]]
        assert [r["path"] for r in basis["manifest"]] == ["design.md", "proposal.md", "tasks.md"]
    state = dispatch({"operation": "initialize", "args": {**args, "owner": "fixture-owner", "mode": "sequential"}})
    directory = expected_root / "execution"
    before = (directory / "state.json").read_bytes()
    assert dispatch({"operation": "read", "args": {"directory": str(directory), "view": "full"}}) == state
    compact = dispatch({"operation": "read", "args": {"directory": str(directory), "view": "compact"}})
    assert compact["available_tasks"] == ["TASK-one"]
    assert (directory / "state.json").read_bytes() == before
    assert list(state["tasks"]) == ["TASK-one"] and state["tasks"]["TASK-one"]["status"] == "pending"
    assert state["final"] is None and state["revision"] == 0
    prefix = expected_root.relative_to(project).as_posix() + "/execution/"
    loaded = read(directory)
    assert not any(name.startswith(prefix) for name in snapshot(loaded)["files"])
    assert expected_root.relative_to(project).as_posix() + "/tasks.md" in loaded["baseline"]["files"]
    javascript = (directory / "dashboard-state.js").read_text(encoding="utf-8")
    view = json.loads(javascript.removeprefix("window.sddApplyUpdate(").removesuffix(");\n"))
    assert view["accepted"] == 0 and view["total"] == 1 and view["final"] is None
    assert view["tasks"][0]["status"] == "pending"
    assert (directory / "dashboard.html").is_file() and "TASK-one" in (directory / "summary.md").read_text(encoding="utf-8")
    if work_kind == "refactoring":
        assert state["acceptance"] == {"AC-local": records[1]}
        assert state["verification"] == {"CHECK-whole": records[2]}
        assert view["work_kind"] == compact["work_kind"] == "refactoring"
        assert view["tasks"][0]["criteria"] == ["AC-local"]
        assert "covers" not in state["tasks"]["TASK-one"]["plan"]


def test_refactoring_inputs_legacy_default_and_ambiguous_selection(project):
    fixtures.approved_refactoring(project)
    args = arguments(project)
    legacy = dict(args)
    legacy.pop("work_kind")
    assert dispatch({"operation": "validate", "args": legacy})["work_kind"] == "change"
    with pytest.raises(ValueError, match="Select work by work_kind and change_id") as error:
        dispatch({"operation": "validate", "args": {**args, "work_kind": None}})
    assert "refactoring" in str(error.value) and "change" in str(error.value)
    assert not (project / "sdd/refactoring/demo/execution").exists()


def test_refactoring_inputs_incomplete_work_still_makes_identity_ambiguous(project):
    root, _, _ = fixtures.approved_refactoring(project)
    (root / "tasks.md").unlink()
    with pytest.raises(Rejected) as error:
        dispatch({"operation": "initialize", "args": {**arguments(project, None), "owner": "fixture-owner"}})
    assert error.value.code == "ambiguous_change"
    assert "'work_kind': 'change'" in str(error.value)
    assert "'work_kind': 'refactoring'" in str(error.value)
    assert "'has_plan': False" in str(error.value)
    assert not (root / "execution").exists()
    assert not (project / "sdd/changes/demo/execution").exists()


@pytest.mark.parametrize("identity,value", [("work_kind", "change"), ("change_id", "another"), ("work_kind", None)])
def test_refactoring_inputs_reject_foreign_approval_even_with_same_manifest(project, identity, value):
    root, users, _ = fixtures.approved_refactoring(project)
    for user in users:
        if value is None:
            user.pop(identity)
        else:
            user[identity] = value
    fixtures.document(root, "review/decisions.md", "decisions", users)
    with pytest.raises(Rejected) as error:
        dispatch({"operation": "initialize", "args": {**arguments(project), "owner": "fixture-owner"}})
    assert error.value.code == "sdd_check"
    diagnostic = json.loads(str(error.value))
    assert diagnostic["approval_status"]["ready"] is False
    assert len(diagnostic["errors"]) == len(users)
    expected = "Authorization change identity mismatch" if identity == "change_id" else "Authorization work kind mismatch"
    assert all(item["code"] == "authorization_structure" and item["message"] == expected
               for item in diagnostic["errors"])
    assert not (root / "execution").exists()


def test_refactoring_inputs_reject_wrong_basis_and_copied_state(project):
    root, _, _ = fixtures.approved_refactoring(project)
    basis = dispatch({"operation": "validate", "args": arguments(project)})
    wrong = copy.deepcopy(basis)
    wrong["work_kind"] = "change"
    with pytest.raises(ValueError, match="outside its registered execution root"):
        initialize(wrong, "fixture-owner")
    assert not (root / "execution").exists()
    dispatch({"operation": "initialize", "args": {**arguments(project), "owner": "fixture-owner"}})
    copied = project / "sdd/changes/demo/execution"
    copied.mkdir()
    shutil.copyfile(root / "execution/state.json", copied / "state.json")
    with pytest.raises(ValueError, match="outside its registered execution root"):
        dispatch({"operation": "read", "args": {"directory": str(copied)}})


@pytest.mark.parametrize("change", ["../demo", "demo/child", "C:/demo", "demo\\child"])
def test_refactoring_inputs_reject_paths_before_writing(project, change):
    with pytest.raises(ValueError):
        dispatch({"operation": "initialize", "args": {**arguments(project), "change": change, "owner": "fixture-owner"}})
    assert not (project / "sdd/refactoring/demo/execution").exists()


def test_refactoring_inputs_schema_and_root_mismatch(project):
    root, _, _ = fixtures.approved_refactoring(project)
    proposal = root / "proposal.md"
    proposal.write_text(proposal.read_text(encoding="utf-8").replace("work_kind: refactoring", "work_kind: change"), encoding="utf-8")
    before = repository(project).inspect()["status"]
    with pytest.raises(ValueError, match="work_kind_mismatch"):
        dispatch({"operation": "validate", "args": arguments(project)})
    assert repository(project).inspect()["status"] == before

pytestmark = pytest.mark.native_state
