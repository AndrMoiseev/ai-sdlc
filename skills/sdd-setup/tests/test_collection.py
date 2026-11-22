import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from setup_collection import check_tools, configure_collection
from setup_progress import progress
from setup_core import PACKAGE


def test_mise_checks_each_binary_and_its_project_provider(monkeypatch):
    project = Path.cwd()
    install = project.parent / "jdk"
    record = {"source": {"path": str(project / "mise.toml")}, "installed": True,
              "active": True, "install_path": str(install)}
    resolved = str(install / "bin/jdeps").encode()
    execute = Mock(side_effect=[json.dumps({"java": [record]}).encode(), resolved])
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    check_tools({"java": ["jdeps"]}, project, execute)
    assert [call.args[0] for call in execute.call_args_list] == [
        ["mise", "ls", "--current", "--json"], ["mise", "which", "jdeps"]]
    record["source"]["path"] = str(project.parent / "global.toml")
    with pytest.raises(ValueError, match="Configure and install java"):
        check_tools({"java": ["jdeps"]}, project, lambda argv: json.dumps({"java": [record]}).encode())


def test_collection_settings_round_trip_and_failed_rerun(tmp_path, monkeypatch):
    # The writer and consumer must agree on the physical settings path, merge,
    # report locations and encoding. Mock the project task, exercise that I/O once.
    monkeypatch.syspath_prepend(str(PACKAGE.parent / "sdd-architect/scripts"))
    import collection
    from audit_configuration import project_collection
    project = tmp_path
    settings = project / ".sdd/settings.json"
    settings.parent.mkdir()
    original = {"schema_version": 1, "subagents": {"roles": {}}, "architect": {"other": 3}}
    settings.write_text(json.dumps(original))
    request = json.loads((PACKAGE / "assets/collection.example.json").read_text())
    request["scope"] = {"source_roots": ["src"], "package_prefixes": ["demo"], "modules": {"demo": ["demo"]},
                        "class_files": {"demo.A": "src/A.kt"}}
    (project / "src").mkdir()
    (project / "src/A.kt").write_text("package demo\nclass A")
    today = datetime.now(timezone.utc).date()
    reports = {
        "dependencies": "", "complexity": '{"runs":[]}',
        "coverage": '<report><package name="demo"><class name="demo/A"/></package></report>',
        "history": json.dumps({"format": "git-history", "first_parent": True, "renames": True,
                               "since": "2000-01-01", "until": today.isoformat(), "commits": []}),
        "sizes": '[{"Name":"Kotlin","Files":[{"Location":"src/A.kt","Lines":2,"Code":2,"Comment":0,"Blank":0}]}]',
        "kotlin": json.dumps({"format": "kotlin-measurements", "version": 2, "complete": True,
                              "tool_version": "1.23.8", "measurement_profile": "kotlin-tokens-functions-1",
                              "files": [{"file": "src/A.kt", "package": "demo", "tokens": [],
                                         "functions": [], "containers": []}]})}
    artifacts = request["collection"]["artifacts"]
    def produce(argv, cwd, policy):
        assert argv == request["collection"]["command"] and cwd == project
        for name, data in reports.items():
            path = project / artifacts[name]["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
    execute = Mock(side_effect=produce)
    monkeypatch.setattr(collection, "run", execute)
    monkeypatch.setattr("setup_collection.check_tools", lambda *args: None)
    assert configure_collection(project, request)["changed"]
    applicable = ["collection", "mise-tasks", "roles"]
    assert progress(project, applicable=applicable, complete="collection", project_changed=True)["stop"]
    assert progress(project, applicable=applicable)["pending_steps"] == ["mise-tasks", "roles"]
    assert project_collection(project) == request["collection"]
    saved = json.loads(settings.read_bytes())
    assert saved["subagents"] == original["subagents"] and saved["architect"]["other"] == 3
    assert saved["setup"] == {"completed_steps": ["collection"]}
    assert not configure_collection(project, request)["changed"]
    before = settings.read_bytes()
    reports["complexity"] = "{}"
    with pytest.raises(ValueError, match="SARIF"):
        configure_collection(project, request)
    assert settings.read_bytes() == before and execute.call_count == 3


def test_project_history_template_tracks_renames(monkeypatch):
    monkeypatch.syspath_prepend(str(PACKAGE / "assets"))
    from history_report import history_report
    raw = b"\x1ebbb\t2026-11-14\0\n1\t0\t\0src/Old.kt\0src/New.kt\0\x1eaaa\t2026-11-13\0\n2\t0\tsrc/Old.kt\0"
    run = Mock(side_effect=[b"false", raw])
    history = history_report(["src"], [], 365, run)
    assert list(history["commits"][1]["changes"]) == ["src/New.kt"]
    assert history["commits"][0]["production_files"] == 1
    assert "--first-parent" in run.call_args.args[0] and "--find-renames" in run.call_args.args[0]
