"""Exercise the progress CLI with settings storage in memory; no subprocesses or project writes."""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import setup
import setup_progress


@pytest.fixture
def progress_cli(monkeypatch, capsys):
    settings = {"schema_version": 1, "architect": {"collection": {}}, "other": "preserve"}
    writes = []
    path = Mock()
    path.exists.return_value = True
    monkeypatch.setattr(setup_progress, "safe_target", lambda *_: path)
    monkeypatch.setattr(setup_progress, "setup_lock", lambda *_: nullcontext())
    monkeypatch.setattr(setup_progress, "read_json", lambda _: deepcopy(settings))

    def replace(_, raw):
        writes.append(raw)
        settings.clear()
        settings.update(json.loads(raw))

    monkeypatch.setattr(setup_progress, "replace_file", replace)

    def invoke(*args):
        monkeypatch.setattr(setup.sys, "argv", ["setup.py", "progress", "--project-root", str(Path.cwd()), *args])
        code = setup.main()
        response = json.loads(capsys.readouterr().out)
        if code:
            raise ValueError(response["message"])
        return response["result"]

    return invoke, settings, writes


def test_changed_lint_step_stops_only_after_checks_pass(progress_cli):
    run, settings, writes = progress_cli
    args = ("--applicable", "ktlint", "detekt")
    assert run(*args)["next_step"] == "ktlint"
    completion = (*args, "--complete", "ktlint", "--project-changed")
    with pytest.raises(ValueError, match="check-exit-code"):
        run(*completion)
    failed = run(*completion, "--check-exit-code", "0", "--check-exit-code", "1")
    assert failed["stop"] and failed["failed_step"] == failed["next_step"] == "ktlint"
    assert not writes
    passed = run(*completion, "--check-exit-code", "0", "--check-exit-code", "0")
    assert passed["stop"] and passed["next_step"] == "detekt" and passed["failed_step"] is None
    assert run(*args)["pending_steps"] == ["detekt"]
    assert settings["architect"] == {"collection": {}} and settings["other"] == "preserve"
    assert len(writes) == 1


def test_only_explicit_reset_reopens_completed_steps(progress_cli):
    run, settings, writes = progress_cli
    settings["setup"] = {"completed_steps": list(setup_progress.STEPS), "other": 42}
    assert run()["pending_steps"] == [] and not writes
    assert run("--reset", "ktlint", "detekt")["pending_steps"] == ["ktlint", "detekt"]
    assert len(writes) == 1
    assert run("--failed", "ktlint")["stop"] and len(writes) == 1
    marker_only = run("--complete", "ktlint", "--check-exit-code", "0")
    assert not marker_only["stop"] and marker_only["next_step"] == "detekt"
    assert run("--reset", "all")["completed_steps"] == []
    assert settings["setup"] == {"completed_steps": [], "other": 42}
    count = len(writes)
    run("--reset", "all")
    assert len(writes) == count


def test_new_or_newly_applicable_step_is_pending(progress_cli, monkeypatch):
    run, settings, writes = progress_cli
    settings["setup"] = {"completed_steps": [s for s in setup_progress.STEPS if s != "detekt"]}
    assert run("--applicable", "common-tools", "roles")["next_step"] is None
    assert run()["next_step"] == "detekt"
    monkeypatch.setattr(setup_progress, "STEPS", ("new-step", *setup_progress.STEPS))
    assert run()["pending_steps"] == ["new-step", "detekt"]
    assert not writes


def test_jacoco_follows_junit_and_precedes_archunit(progress_cli):
    run, _, _ = progress_cli
    args = ("--applicable", "archunit", "jacoco", "junit5")
    assert run(*args)["pending_steps"] == ["junit5", "jacoco", "archunit"]
    assert run(*args, "--complete", "junit5")["next_step"] == "jacoco"


def test_runtime_tools_are_outside_project_progress(progress_cli):
    run, _, writes = progress_cli
    pending = run()["pending_steps"]
    assert pending[0] == "common-tools"
    for tool in ("mise", "uv"):
        assert tool not in pending
        with pytest.raises(SystemExit) as rejected:
            run("--complete", tool)
        assert rejected.value.code == 2
    assert not writes


def test_invalid_progress_preserves_settings(progress_cli):
    run, settings, writes = progress_cli
    settings["setup"] = {"completed_steps": "ktlint"}
    with pytest.raises(ValueError, match="distinct step names"):
        run("--reset", "all")
    assert not writes
