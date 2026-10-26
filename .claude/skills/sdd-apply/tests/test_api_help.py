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
    assert {"role_id", "successor", "task_id", "reason", "evidence"} == set(result["resolution"])
    assert any("successor_of" in rule for rule in result["rules"])


@pytest.mark.parametrize("args", [{"operation": "missing"}, {"event": "missing"},
                                  {"operation": "read", "event": "resume"}])
def test_help_rejects_invalid_selectors(args):
    with pytest.raises(ValueError):
        describe(**args)


@pytest.mark.parametrize("args,key,expected", [
    (["--help-event", "resume"], "event", "resume"),
    (["--help-operation", "read"], "operation", "read"),
    (["--help-operation"], "events", None),
])
def test_cli_help_needs_no_request_or_project(tmp_path, args, key, expected):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/execute.py"), *args],
                            cwd=tmp_path, capture_output=True, shell=False, timeout=30)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    if expected is None:
        assert "resume" in payload["result"][key]
    else:
        assert payload["result"][key] == expected
    assert list(tmp_path.iterdir()) == []
