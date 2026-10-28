import json
from pathlib import Path
import subprocess
import sys
import pytest
from lib.api import dispatch
from lib.api_help import describe

ROOT = Path(__file__).resolve().parents[1]


def test_help_covers_event_schema_without_accessing_execution_state(monkeypatch):
    from lib import state
    def unexpected(*args, **kwargs):
        pytest.fail("Read-only help attempted to open an execution")
    monkeypatch.setattr(state, "read", unexpected)
    index = dispatch({"operation": "help"})
    schema = json.loads((ROOT / "schemas/event.schema.json").read_text())
    assert set(index["events"]) == set(schema["properties"]["type"]["enum"])
    for name in index["events"]:
        result = dispatch({"operation": "help", "args": {"event": name}})
        assert result["event"] == name and result["summary"]
        assert set(result["envelope"]) == set(schema["required"])
    for name in index["operations"]:
        assert dispatch({"operation": "help", "args": {"operation": name}})["summary"]


def test_resume_help_explains_specific_loss_and_legacy_resolution():
    result = describe(event="resume")
    assert set(result["required"]) == {"host_trace", "live_contexts"}
    assert {"role_id", "successor", "task_id", "reason", "evidence", "head", "instruction"} == set(result["resolution"])
    assert any("successor_of" in rule for rule in result["rules"])


def test_ordinary_project_final_help_preserves_task_finals_and_followup_budgets():
    registration = describe(event="checks_register")
    assert registration["task_id"] == "TASK-ID or null"
    assert any("after all tasks are accepted" in rule for rule in registration["rules"])
    assert any("Task-scoped final checks still apply" in rule for rule in registration["rules"])
    revision = describe(event="revised_plan")
    assert "completed_followups" in revision["optional"]
    assert set(revision["completed_followups"][0]) == {"completed_task", "followup_task"}
    assert any("counters and unrelated blockers remain" in rule for rule in revision["rules"])
    assert any("obligations survive revision" in rule for rule in revision["rules"])


@pytest.mark.parametrize("args", [{"operation": "missing"}, {"event": "missing"},
                                  {"operation": "read", "event": "resume"}])
def test_help_rejects_invalid_selectors(args):
    with pytest.raises(ValueError):
        describe(**args)


@pytest.mark.parametrize("args,key,expected,native", [
    # One fresh interpreter proves imports and executable entrypoint wiring.
    pytest.param(["--help-event", "resume"], "event", "resume", True, marks=pytest.mark.native_process),
    (["--help-operation", "read"], "operation", "read", False),
    (["--help-operation"], "events", None, False),
])
def test_cli_help_needs_no_request_or_project(tmp_path, monkeypatch, capsys, args, key, expected, native):
    if native:
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/execute.py"), *args],
                                cwd=tmp_path, capture_output=True, shell=False, timeout=30)
        assert result.returncode == 0, result.stderr
        output = result.stdout
    else:
        from execute import main
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["execute.py", *args])
        assert main() == 0
        output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["ok"] is True
    if expected is None:
        assert "resume" in payload["result"][key]
    else:
        assert payload["result"][key] == expected
    assert list(tmp_path.iterdir()) == []
