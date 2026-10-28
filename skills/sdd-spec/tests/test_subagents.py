"""Project role selection, independently of any running model service."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from lib.subagents import ConfigurationError, ROLES, resolve, validate_selection


ROLE = "sdd-spec.document_reviewer"


def configure(root, roles=None, **extra):
    path = root / ".sdd/settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "subagents": {"roles": roles or {}},
                                **extra}), encoding="utf-8")
    return path


def agent(root, filename="review.toml", name="reviewer", fields='model = "gpt-6-luna"\nmodel_reasoning_effort = "high"'):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_text(f'name = "{name}"\ndescription = "Reviews assigned material"\n'
                    'developer_instructions = "UNAPPLIED_PROFILE_INSTRUCTIONS"\n' + fields,
                    encoding="utf-8")
    return path


def select(root, **kwargs):
    return resolve(root, ROLE, "codex", "parent-model", "medium",
                   user_agent_dir=root / "user-agents", **kwargs)


@pytest.mark.parametrize("case", ["no_file", "no_role", "missing_agent"])
def test_parent_fallback_has_explicit_model_and_effort(tmp_path, case):
    if case != "no_file":
        configure(tmp_path, {ROLE: "missing"} if case == "missing_agent" else {})
    result = select(tmp_path)
    assert result["launch"] == {"model": "parent-model", "reasoning_effort": "medium", "fork_turns": "none"}
    assert result["mode"] == "parent"
    assert bool(result["warnings"]) == (case == "missing_agent")


def test_project_profile_by_name_wins_and_does_not_import_instructions(tmp_path):
    configure(tmp_path, {ROLE: "reviewer"})
    agent(tmp_path / "user-agents", fields='model = "wrong-user-model"')
    path = agent(tmp_path / ".codex/agents", filename="unrelated-filename.toml")
    result = select(tmp_path)
    assert result["launch"] == {"fork_turns": "none", "model": "gpt-6-luna", "reasoning_effort": "high"}
    assert result["definition"]["path"] == str(path.resolve())
    assert result["definition"]["ignored_fields"] == ["developer_instructions"]
    assert "UNAPPLIED_PROFILE_INSTRUCTIONS" not in json.dumps(result)
    assert result["settings"]["sha256"] and result["definition"]["sha256"]
    validate_selection(result, tmp_path, ROLE, "codex")


def test_user_profile_and_codex_home(tmp_path, monkeypatch):
    configure(tmp_path, {ROLE: "reviewer"})
    root = tmp_path / "custom-home"
    monkeypatch.setenv("CODEX_HOME", str(root))
    agent(root / "agents")
    result = resolve(tmp_path, ROLE, "codex", "parent-model")
    assert result["launch"]["model"] == "gpt-6-luna"


@pytest.mark.parametrize("fields,expected", [
    ('', {"model": "parent-model", "reasoning_effort": "medium"}),
    ('model = "inherit"', {"model": "parent-model", "reasoning_effort": "medium"}),
    ('model = "other-model"', {"model": "other-model"}),
    ('model_reasoning_effort = "high"', {"model": "parent-model", "reasoning_effort": "high"}),
])
def test_model_and_effort_inheritance(tmp_path, fields, expected):
    configure(tmp_path, {ROLE: "reviewer"})
    agent(tmp_path / ".codex/agents", fields=fields)
    assert select(tmp_path)["launch"] == {"fork_turns": "none", **expected}


@pytest.mark.parametrize("data", [
    [], {"schema_version": True}, {"schema_version": 2},
    {"schema_version": 1, "subagents": []},
    {"schema_version": 1, "subagents": {"models": {}}},
    {"schema_version": 1, "subagents": {"roles": []}},
    {"schema_version": 1, "subagents": {"roles": {"sdd-apply.revewer": "x"}}},
    {"schema_version": 1, "subagents": {"roles": {ROLE: None}}},
    {"schema_version": 1, "subagents": {"roles": {ROLE: " "}}},
])
def test_invalid_settings_are_errors(tmp_path, data):
    path = configure(tmp_path)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        select(tmp_path)


@pytest.mark.parametrize("text", ['{', '{"schema_version":1,"schema_version":1}'])
def test_malformed_or_duplicate_json_is_not_missing(tmp_path, text):
    path = configure(tmp_path)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        select(tmp_path)


@pytest.mark.parametrize("fields", ['model = 3', 'model = ""', 'model_reasoning_effort = 2', 'invalid = ['])
def test_invalid_profile_is_not_missing(tmp_path, fields):
    configure(tmp_path, {ROLE: "reviewer"})
    agent(tmp_path / ".codex/agents", fields=fields)
    with pytest.raises(ConfigurationError):
        select(tmp_path)


def test_duplicate_names_are_rejected(tmp_path):
    configure(tmp_path, {ROLE: "reviewer"})
    for filename in ("a.toml", "b.toml"):
        agent(tmp_path / ".codex/agents", filename=filename)
    with pytest.raises(ConfigurationError, match="Duplicate agent name"):
        select(tmp_path)


def test_other_top_level_settings_and_all_role_ids(tmp_path):
    configure(tmp_path, {role: "reviewer" for role in ROLES}, unrelated={"future": True})
    agent(tmp_path / ".codex/agents")
    for role in ROLES:
        assert resolve(tmp_path, role, "codex", "parent")["mode"] == "model-profile"


def test_claude_native_selection_uses_observed_catalog_not_disk(tmp_path):
    configure(tmp_path, {ROLE: "plugin:reviewer"})
    result = resolve(tmp_path, ROLE, "claude-code", "parent", available_agents=["plugin:reviewer"])
    assert result["mode"] == "native-agent"
    assert result["launch"] == {"subagent_type": "plugin:reviewer"}
    validate_selection(result, tmp_path, ROLE, "claude-code")


@pytest.mark.parametrize("mapped", [False, True])
def test_claude_fallback_explicitly_requests_parent(tmp_path, mapped):
    configure(tmp_path, {ROLE: "missing"} if mapped else {})
    result = resolve(tmp_path, ROLE, "claude-code", "parent", available_agents=["general-purpose"])
    assert result["launch"] == {"subagent_type": "general-purpose", "model": "parent"}


@pytest.mark.parametrize("catalog", [None, [], "general-purpose", [None]])
def test_claude_catalog_or_fallback_unavailable(tmp_path, catalog):
    with pytest.raises(ConfigurationError):
        resolve(tmp_path, ROLE, "claude-code", "parent", available_agents=catalog)


def test_settings_and_definition_changes_detected_before_registration(tmp_path):
    configure(tmp_path, {ROLE: "reviewer"})
    path = agent(tmp_path / ".codex/agents")
    result = select(tmp_path)
    path.write_text(path.read_text() + '\n# changed\n', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="definition changed"):
        validate_selection(result, tmp_path, ROLE, "codex")
    configure(tmp_path)
    with pytest.raises(ConfigurationError, match="settings changed"):
        validate_selection(result, tmp_path, ROLE, "codex")


def test_cli_runs_without_import_side_effects(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/resolve_agent.py"
    result = subprocess.run([sys.executable, "-B", str(script), "--project-root", str(tmp_path),
                             "--host", "codex", "--role", ROLE, "--parent-model", "parent"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["launch"]["model"] == "parent"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("host", ["codex", "claude-code"])
def test_probe_preparation_is_separate_and_does_not_launch(host, tmp_path):
    from prepare_subagent_eval import prepare
    output = tmp_path / "probe"
    result = prepare(output, host)
    assert result["status"] == "prepared"
    assert json.loads((output / "evidence.json").read_text())["status"] == "not_run"
    assert not (output / "project/evidence.json").exists()
    suffix = ".codex/agents/arithmetic.toml" if host == "codex" else ".claude/agents/arithmetic.md"
    assert (output / "project" / suffix).is_file()
    with pytest.raises(ValueError, match="new output"):
        prepare(output, host)


@pytest.mark.parametrize("script", ["resolve_agent.py", "prepare_subagent_eval.py"])
def test_new_entrypoints_relocate_without_consumer_changes(tmp_path, script, installed_packages):
    import os
    installed = installed_packages / "sdd-spec"
    consumer = tmp_path / "conflicting consumer"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text('[project]\nname="conflict"\nversion="1.0"\n'
        'requires-python=">=3.11"\ndependencies=["nonexistent-sdd-test-dependency==0"]\n')
    before = {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    consumer_before = (consumer / "pyproject.toml").read_bytes()
    env = dict(os.environ, UV_CACHE_DIR=str(tmp_path / "empty-uv-cache"))
    # Both new scripts use stdlib only: an empty offline cache should succeed.
    for _ in range(2):
        result = subprocess.run(["uv", "run", "--locked", "--offline", "--python", sys.executable,
                                 "--script", str(installed / "scripts" / script), "--help"],
                                cwd=consumer, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
    assert before == {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    assert list(consumer.iterdir()) == [consumer / "pyproject.toml"]
    assert (consumer / "pyproject.toml").read_bytes() == consumer_before


def test_resolver_lock_does_not_silently_update(tmp_path):
    import shutil
    script = Path(__file__).resolve().parents[1] / "scripts/resolve_agent.py"
    copy = tmp_path / script.name
    shutil.copy2(script, copy)
    lock = copy.with_suffix(".py.lock")
    shutil.copy2(script.with_suffix(".py.lock"), lock)
    original = lock.read_bytes()
    copy.write_text(copy.read_text().replace('# requires-python = ">=3.11"', '# requires-python = ">=3.12"'))
    result = subprocess.run(["uv", "run", "--locked", "--offline", "--script", str(copy), "--help"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "lock" in result.stderr.lower()
    assert lock.read_bytes() == original


@pytest.mark.parametrize("initial", ["user", "missing"])
def test_catalog_precedence_and_missing_agent_rechecked(tmp_path, initial):
    configure(tmp_path, {ROLE: "reviewer"})
    if initial == "user":
        agent(tmp_path / "user-agents")
    selected = select(tmp_path)
    agent(tmp_path / ".codex/agents", fields='model = "new-project-model"')
    with pytest.raises(ConfigurationError, match="catalog or launch selection changed"):
        validate_selection(selected, tmp_path, ROLE, "codex")


def test_unreadable_settings_are_not_missing(tmp_path, monkeypatch):
    original = Path.read_bytes
    def denied(path):
        if path.name == "settings.json":
            raise PermissionError("denied settings")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(PermissionError, match="denied settings"):
        select(tmp_path)


def test_unreadable_catalog_is_not_missing(tmp_path, monkeypatch):
    configure(tmp_path, {ROLE: "reviewer"})
    original = Path.iterdir
    def denied(path):
        if path.name == "agents":
            raise PermissionError("denied catalog")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(PermissionError, match="denied catalog"):
        select(tmp_path)
