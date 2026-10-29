"""Current reads validate accessed data; complete history has an explicit audit."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from lib.api import dispatch
from lib.common import write_json
from lib.state import apply, read, seal, save, audit, inspect
from lib.state_storage import storage


def compact(driver):
    return dispatch({"operation": "read", "args": {
        "directory": str(driver.directory), "view": "compact",
    }})


def envelope(view, ident, **changes):
    return {"event_id": ident, "run_id": view["run_id"],
            "expected_revision": view["revision"],
            "type": "block", "task_id": "TASK-one",
            "payload": {"reason": "test", "resume_condition": "fixed"}, **changes}


@pytest.mark.native_state
def test_default_full_and_compact_are_read_only(driver):
    path = driver.directory / "state.json"
    before = path.read_bytes()
    full = dispatch({"operation": "read", "args": {"directory": str(driver.directory), "view": "full"}})
    assert full == json.loads(before)
    assert dispatch({"operation": "read", "args": {"directory": str(driver.directory)}}) == compact(driver)
    view = compact(driver)
    assert view["view"] == "compact" and view["view_version"] == 1
    assert view["revision"] == full["revision"]
    assert view["available_tasks"] == ["TASK-one"]
    assert view["artifacts"] == {"state": "state.json", "run": f"runs/{full['run_id']}"}
    assert not {"events", "basis", "roles", "baseline", "final"} & view.keys()
    assert path.read_bytes() == before
    # Scheduler eligibility alone cannot bypass the event's registry gate.
    with pytest.raises(ValueError, match="Register planned and project checks"):
        apply(driver.directory, envelope(view, "start", type="start", payload={}))
    assert path.read_bytes() == before


def test_compact_preserves_blockers_budgets_and_active_roles(execution_checkpoint):
    driver = execution_checkpoint("started")
    view = compact(driver)
    assert view["active_roles"] == {
        "author": {"kind": "executor", "task_id": "TASK-one", "context_id": "author"},
    }
    driver.send("block", {"reason": "needs decision", "resume_condition": "user answers"}, task_id=None)
    view = compact(driver)
    full = driver.state
    assert view["status"] == "blocked" and view["available_tasks"] == []
    assert view["blockers"] == full["blockers"]
    assert view["tasks"]["TASK-one"] == {
        **{key: full["tasks"]["TASK-one"][key] for key in view["tasks"]["TASK-one"] if key != "verification"},
        "verification": view["tasks"]["TASK-one"]["verification"],
    }
    # Nondefault counters/reservations must not disappear from the projection.
    full["tasks"]["TASK-one"].update(review_limit=6, review_rounds_started=4,
        review_rounds_completed=3, active_review="round-4", test_repair_limit=9,
        test_repair_cycles_started=7, active_repair="cycle-7")
    seal(full)
    save(driver.directory, full)
    task = compact(driver)["tasks"]["TASK-one"]
    assert task["active_review"] == "round-4" and task["active_repair"] == "cycle-7"
    assert task["review_limit"] == 6 and task["test_repair_limit"] == 9
    assert task["review_rounds_started"] == 4 and task["review_rounds_completed"] == 3
    assert task["test_repair_cycles_started"] == 7


@pytest.mark.parametrize("damage,reseal,error", [
    ("integrity", False, "state_corrupt"),
    ("version", True, "state_version"),
    ("status", True, "state_schema"),
    ("task_status", True, "state_schema"),
    ("length", True, "history_corrupt"),
])
@pytest.mark.parametrize("view", ["full", "compact"])
def test_both_views_validate_current_manifest(driver, damage, reseal, error, view):
    driver.send("block", {"reason": "test", "resume_condition": "fixed"})
    data = driver.state
    if damage == "integrity":
        data["updated_at"] = "tampered"
    elif damage == "version":
        data["schema_version"] = 1
    elif damage == "status":
        data["status"] = "unknown"
    elif damage == "task_status":
        data["tasks"]["TASK-one"]["status"] = "unknown"
    elif damage == "length":
        data["revision"] += 1
    if reseal:
        seal(data)
    save(driver.directory, data)
    with pytest.raises(ValueError) as rejected:
        dispatch({"operation": "read", "args": {"directory": str(driver.directory), "view": view}})
    assert rejected.value.code == error


@pytest.mark.parametrize("view", ["full", "compact"])
@pytest.mark.native_state
@pytest.mark.native_paths
def test_read_rejects_copied_state_root(driver, tmp_path, view):
    copied = tmp_path / "wrong-root"
    copied.mkdir()
    shutil.copyfile(driver.directory / "state.json", copied / "state.json")
    with pytest.raises(ValueError, match="outside its registered execution root"):
        read(copied, view=view)


def test_compact_revision_conflict_and_identical_retry(driver):
    initial = compact(driver)
    item = envelope(initial, "first")
    result = apply(driver.directory, item)
    current = compact(driver)
    assert current["revision"] == initial["revision"] + 1
    saved = storage(driver.directory).read()
    with pytest.raises(ValueError, match="Re-read current state"):
        apply(driver.directory, envelope(initial, "stale"))
    assert apply(driver.directory, item) == result
    with pytest.raises(ValueError, match="Event ID reused"):
        apply(driver.directory, {**item, "expected_revision": current["revision"]})
    assert storage(driver.directory).read() == saved
    apply(driver.directory, envelope(current, "fresh"))
    assert compact(driver)["revision"] == current["revision"] + 1


def test_compact_size_does_not_repeat_finished_role_history(driver):
    # Real accepted events, with verbose completed reports retained in full.
    sizes = []
    manifest_sizes = []
    for number in range(12):
        ident = f"author-{number}"
        driver.role(ident, "executor")
        driver.send("role_result", {"role_id": ident,
            "result": {"report": "retained report details " * 150}, "trace": "test-host"})
        view = compact(driver)
        sizes.append(len(json.dumps(view)))
        manifest_sizes.append(len(storage(driver.directory).read()))
        assert view["active_roles"] == {}
    full_size = len(json.dumps(driver.state))
    assert max(sizes) - min(sizes) < 16  # Only revision digits / timestamp precision.
    assert max(manifest_sizes) - min(manifest_sizes) < 256
    assert sizes[-1] < full_size / 10
    assert audit(driver.directory)["events"] == 24
    assert driver.state["roles"]["author-0"]["result"]["report"]


@pytest.mark.parametrize("view,success", [("compact", True), ("full", True), ("short", False)])
@pytest.mark.native_state
def test_cli_read_view(driver, tmp_path, view, success):
    request = tmp_path / "read-request.json"
    write_json(request, {"operation": "read", "args": {
        "directory": str(driver.directory), "view": view,
    }})
    script = Path(__file__).resolve().parents[1] / "scripts/execute.py"
    result = subprocess.run(["uv", "run", "--locked", "--script", str(script),
                             "--request", str(request)], cwd=tmp_path,
                            capture_output=True, timeout=60)
    response = json.loads(result.stdout)
    assert response["ok"] is success
    assert result.returncode == (0 if success else 1)
    if success:
        assert response["result"] == inspect(driver.directory, view=view)
    else:
        assert response["code"] == "read_view"


def test_execution_and_conclusion_are_visible_separately_without_raw_logs(execution_checkpoint, monkeypatch):
    """AC-explorer-visibility: both read/dashboard projections expose the proof pair."""
    from lib import artifact_storage
    from lib.dashboard import projection, static_waves
    driver = execution_checkpoint("frozen")
    driver.explorer("visible-explorer", "independent")
    driver.send("check_run", {"role_id": "visible-explorer", "stage": "independent"})
    driver.send("role_result", {"role_id": "visible-explorer", "result": "DONE", "trace": "synthetic host"})
    view = compact(driver)
    proof = view["tasks"]["TASK-one"]["verification"]["independent"]
    assert proof["execution"]["status"] == "passed"
    assert proof["conclusion"]["status"] == "missing"
    role = next(item for item in view["explorer_assignments"] if item["stage"] == "independent")
    assert role["scope"]["task"] == "TASK-one" and role["status"] == "finished"
    driver.role("assessment", "verifier")
    driver.conclude(role="assessment")
    original = artifact_storage.read_bytes
    def no_raw_logs(path):
        assert "/runs/" not in str(path).replace("\\", "/"), "Projection opened an execution log"
        return original(path)
    monkeypatch.setattr(artifact_storage, "read_bytes", no_raw_logs)
    view = compact(driver)
    assert view["tasks"]["TASK-one"]["verification"]["independent"]["conclusion"]["status"] == "passed"
    data = projection(driver.state)
    assert data["tasks"][0]["verification"] == view["tasks"]["TASK-one"]["verification"]
    html = static_waves(data)
    assert "Execution passed" in html and "Conclusion passed" in html and "visible-explorer" in html
    assert "<details" not in html


def test_conclusion_history_is_externalized_and_roundtrips(driver):
    """AC-explorer-resume/visibility: schema 3 keeps actual conclusions in objects."""
    from lib.state_objects import StateObjects
    state = driver.state
    state["tasks"]["TASK-one"]["verification_results"] = [{"id": "historical", "stage": "independent", "outcome": "failed"}]
    packed = StateObjects(driver.directory).pack(state, root=True)
    reference = packed["tasks"]["TASK-one"]["verification_results"]
    assert set(reference) == {"$object"}
    opened = StateObjects(driver.directory).open(packed)
    assert opened["tasks"]["TASK-one"]["verification_results"] == state["tasks"]["TASK-one"]["verification_results"]
    assert packed["schema_version"] == 3


def test_prepared_sync_read_fixtures_require_both_final_proofs():
    """AC-explorer-visibility: deterministic fixture validation, not a sync agent eval."""
    root = Path(__file__).resolve().parents[2] / "sdd-sync"
    fixture = json.loads((root / "evals/explorer-read-fixtures.json").read_text(encoding="utf-8"))
    assert fixture["criteria"] == ["AC-explorer-visibility"]
    assert fixture["behavioral_result"] == "not_run"
    assert {item["name"] for item in fixture["cases"]} == {"complete-pair", "command-only", "missing-execution", "stale-conclusion", "partial"}
    for case in fixture["cases"]:
        view = case["response"]["result"]
        proof = view["tasks"]["TASK-one"]["verification"]["final"]
        eligible = (view["status"] == "completed" and view["completion"]["result"] == "complete"
                    and view["tasks"]["TASK-one"]["status"] == "accepted"
                    and proof["execution"]["status"] == proof["conclusion"]["status"] == "passed")
        assert eligible == case["expected_eligible"]
        assert bool(proof["execution"]["references"]) == (proof["execution"]["status"] == "passed")
        assert proof["execution"]["checks"][0]["status"] == proof["execution"]["status"]
        assert bool(proof["conclusion"]["id"]) == (proof["conclusion"]["status"] != "missing")
    manual = (root / "evals/manual.md").read_text(encoding="utf-8")
    workflow = (root / "references/workflow.md").read_text(encoding="utf-8")
    assert "explorer-read-fixtures.json" in manual and "AC-explorer-visibility" in manual
    assert "verification_results" in workflow and "read_object" in workflow


@pytest.mark.parametrize("replacement", ["successor", "new_assignment"])
@pytest.mark.parametrize("clock", ["equal", "backward"])
def test_latest_explorer_survives_sorted_storage_and_clock_changes(driver, monkeypatch, replacement, clock):
    """AC-explorer-visibility: event revisions, not IDs or wall time, order roles."""
    from lib import roles
    from lib.dashboard import projection
    from lib.state import read
    observed = ["2026-10-29T12:00:00Z"]
    monkeypatch.setattr(roles, "now", lambda: observed[0])
    driver.explorer("z-old")
    if replacement == "successor":
        driver.send("resume", {"host_trace": "synthetic loss", "live_contexts": []}, task_id=None)
    else:
        driver.send("role_result", {"role_id": "z-old", "trace": "synthetic completion",
            "result": {"kind": "research", "answer": "Inspected", "references": [], "inspected_scope": ["check.py"],
                       "limitations": [], "assumptions": [], "questions": []}})
    if clock == "backward":
        observed[0] = "2026-10-29T11:00:00Z"
    driver.explorer("a-new", **({"successor_of": "z-old"} if replacement == "successor" else {}))
    saved = read(driver.directory)
    assert list(saved["roles"]) == ["a-new", "z-old"]
    assert saved["roles"]["a-new"]["registered_revision"] > saved["roles"]["z-old"]["registered_revision"]
    for view in (compact(driver), projection(read(driver.directory))):
        assert len(view["explorer_assignments"]) == 1
        current = view["explorer_assignments"][0]
        assert (current["role_id"], current["scope"]["task"], current["kind"], current["stage"], current["status"]) == (
            "a-new", "TASK-one", "research", None, "active")


def assert_run_progress_uses_metadata(driver, monkeypatch, field):
    """Shared memory contract; guard run logs and raw/report immutable objects."""
    from lib import artifact_storage, check_evidence
    from lib.dashboard import projection
    from lib.state import read
    from lib.state_objects import StateObjects
    state = driver.state
    objects = StateObjects(driver.directory)
    raw_hashes = set()
    for item in state["final_checks"]["evidence"]:
        if item.get("procedure"):
            continue
        record = json.loads(artifact_storage.read_bytes(driver.directory / item["log"]))
        for output in record["outputs"]:
            summary = objects.get(output["summary"])
            raw_hashes.update(ref["sha256"] for ref in summary.get("artifacts", {}).values())
            raw_hashes.update(report["reference"]["sha256"] for report in summary.get("structured_reports", [])
                              if report.get("reference"))
    assert raw_hashes, "Fixture must contain actual recorded raw stream references"
    original_read, original_get = artifact_storage.read_bytes, StateObjects.get
    def metadata_only(path):
        assert "/runs/" not in str(path).replace("\\", "/"), "Progress opened a run log"
        return original_read(path)
    def no_raw_object(self, reference):
        assert reference["sha256"] not in raw_hashes, "Progress opened raw stream/report evidence"
        result = original_get(self, reference)
        assert not (isinstance(result, dict) and "identity" in result and "stream" in result), "Progress expanded raw evidence"
        return result
    def no_acceptance_audit(*args, **kwargs):
        pytest.fail("Read projection invoked the raw acceptance validator")
    monkeypatch.setattr(artifact_storage, "read_bytes", metadata_only)
    monkeypatch.setattr(StateObjects, "get", no_raw_object)
    monkeypatch.setattr(check_evidence, "validate", no_acceptance_audit)
    compact_view, dashboard_view = compact(driver), projection(read(driver.directory))
    assert compact_view[field] == dashboard_view[field]
    assert compact_view[field]["execution"]["status"] == "passed"
    assert compact_view[field]["conclusion"]["status"] == "passed"
    assert compact_view[field]["confirmed_criteria"]
