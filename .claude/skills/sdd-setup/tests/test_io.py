import json
from pathlib import Path
import subprocess
import sys

import pytest
import setup_core as core
import setup_io


def cli(*args, cwd=None):
    run = subprocess.run([sys.executable, "-B", str(core.PACKAGE / "scripts/setup.py"), *map(str, args)],
                         shell=False, cwd=cwd, capture_output=True, encoding="utf-8", timeout=30)
    body = json.loads(run.stdout)
    assert body["ok"] == (run.returncode == 0), run.stderr
    return body


def inspection(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    return core.inspect_project(project, "codex", user_agent_dir=tmp_path / "user")


def request_for(view):
    return {"inspection": view, "roles": {row["role"]: {"action": "default"} for row in view["roles"]},
            "agents": {row["default"]: {"model": {"action": "default"}, "effort": {"action": "default"}}
                       for row in view["roles"]}}


def file_request(tmp_path, view):
    receipt = setup_io.save_result(view, tmp_path / "inspection.json", "inspect")
    request = request_for(view)
    request.pop("inspection")
    request.update(inspection_file="inspection.json", inspection_sha256=receipt["sha256"])
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path


def test_cli_file_roundtrip_keeps_exact_diff_recovery_and_legacy_contract(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    artifact = tmp_path / "inspection.json"
    args = ["inspect", "--project-root", project, "--host", "codex", "--user-agent-dir", tmp_path / "user"]
    receipt = cli(*args, "--output", artifact)["result"]
    view = core.read_json(artifact)
    assert cli(*args)["result"] == view
    assert receipt["sha256"] == core.digest(artifact.read_bytes())
    assert receipt["summary"]["roles"] == view["roles"]
    assert "inputs" not in receipt["summary"] and "evidence" not in receipt["summary"]
    request = request_for(view)
    legacy_size = len(json.dumps(request))
    request.pop("inspection")
    request.update(inspection_file="inspection.json", inspection_sha256=receipt["sha256"])
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    assert len(json.dumps(request)) < legacy_size / 2
    artifact_plan = tmp_path / "plan.json"
    # Relative references belong to the request directory, regardless of process cwd.
    planned = cli("plan", "--request", request_path, "--output", artifact_plan, cwd=project)["result"]
    plan = core.read_json(artifact_plan)
    assert cli("plan", "--request", request_path)["result"] == plan
    assert plan["request"] == request_for(view)
    assert planned["summary"]["operations"] == [{"path": op["path"], "diff": op["diff"]} for op in plan["operations"]]
    assert all("after" in op and "before" in op for op in plan["operations"])
    for row in view["roles"]:
        selected = planned["summary"]["selected_agents"][row["default"]]
        assert selected["scope"] == "project"
        assert selected["model"] == row["profile_default"]["model"]
        assert selected["effort"] == row["profile_default"]["effort"]
    assert len(json.dumps(planned)) < len(json.dumps(plan)) * 0.6
    assert not list(project.iterdir())
    # Plans are self-contained; neither request nor source artifact is needed at apply.
    artifact.unlink()
    request_path.unlink()
    applied = cli("apply", "--plan", artifact_plan)["result"]
    assert set(applied["changed"]) == {op["path"] for op in plan["operations"]}


def test_file_request_keeps_project_freshness_check(tmp_path):
    view = inspection(tmp_path)
    path = file_request(tmp_path, view)
    settings = Path(view["project_root"]) / ".sdd/settings.json"
    settings.parent.mkdir()
    settings.write_text('{"schema_version":1,"changed":true}', encoding="utf-8")
    result = cli("plan", "--request", path, "--output", tmp_path / "plan.json")
    assert not result["ok"] and "changed" in result["message"]
    assert not (tmp_path / "plan.json").exists()


def test_changed_source_hash_is_rejected(tmp_path):
    path = file_request(tmp_path, inspection(tmp_path))
    with (tmp_path / "inspection.json").open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="Inspection file changed"):
        setup_io.read_request(path)


@pytest.mark.parametrize("change", [
    {"inspection": {}}, {"inspection_sha256": "invalid"}, {"inspection_file": ""},
    {"inspection_file": "missing.json"}, {"inspection_file": "."},
])
def test_invalid_or_ambiguous_file_request_is_rejected(tmp_path, change):
    path = file_request(tmp_path, inspection(tmp_path))
    request = core.read_json(path) | change
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        setup_io.read_request(path)


@pytest.mark.parametrize("destination", ["project/new.json", "skills/run.json", "artifact.txt", "missing/run.json"])
def test_output_rejects_project_package_or_invalid_paths_without_writes(tmp_path, destination):
    view = inspection(tmp_path)
    (tmp_path / "skills").mkdir()
    with pytest.raises(ValueError):
        setup_io.save_result(view, tmp_path / destination, "inspect")
    assert not (tmp_path / destination).exists()


def test_output_does_not_overwrite_or_write_inside_named_package(tmp_path):
    view = inspection(tmp_path)
    occupied = tmp_path / "occupied.json"
    occupied.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        setup_io.save_result(view, occupied, "inspect")
    assert occupied.read_text(encoding="utf-8") == "preserve"
    package = tmp_path / "custom-package"
    package.mkdir()
    (package / "SKILL.md").write_text("# Fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="skill packages"):
        setup_io.save_result(view, package / "artifact.json", "inspect")


def test_plan_summary_retains_native_unknown_and_explicit_inheritance(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    view = core.inspect_project(project, "claude-code", user_agent_dir=tmp_path / "user",
                                available_agents=["sdd-executor"])
    request = request_for(view)
    request["agents"]["sdd-executor"] = {"model": {"action": "keep"}, "effort": {"action": "keep"}}
    request["agents"]["sdd-reviewer"] = {"model": {"action": "set", "value": None},
                                          "effort": {"action": "set", "value": None}}
    selected = setup_io.plan_summary(core.make_plan(request))["selected_agents"]
    assert selected["sdd-executor"]["scope"] == "native"
    assert selected["sdd-executor"]["model"] is None
    assert selected["sdd-reviewer"]["model"] is None
    assert selected["sdd-reviewer"]["effort"] is None
