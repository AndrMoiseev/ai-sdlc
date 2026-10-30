import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import setup_core as core


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def inspect(tmp_path, host="codex", **kwargs):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    return core.inspect_project(project, host, user_agent_dir=tmp_path / "user",
                                available_agents=["general-purpose"] if host == "claude-code" else None,
                                **kwargs)


def defaults(view):
    return {"inspection": view, "roles": {r["role"]: {"action": "default"} for r in view["roles"]},
            "agents": {r["default"]: {"model": {"action": "default"}, "effort": {"action": "default"}}
                       for r in view["roles"]}}


def keep(view):
    return {"inspection": view, "roles": {r["role"]: {"action": "keep"} if r["present"] else {"action": "set", "value": None} for r in view["roles"]},
            "agents": {r["current"]: {field: {"action": "set", "value": None}
                                      if view["agents"][r["current"]][field] is None
                                      and view["agents"][r["current"]]["scope"] != "native"
                                      else {"action": "keep"} for field in ("model", "effort")}
                       for r in view["roles"] if r["current"]}}


@pytest.mark.parametrize("host", ["codex", "claude-code"])
def test_fresh_defaults_apply_and_repeat_keep(tmp_path, host):
    view = inspect(tmp_path, host)
    plan = core.make_plan(defaults(view))
    project = Path(view["project_root"])
    assert not list(project.iterdir()), "Inspect and plan must be read-only"
    assert len(plan["operations"]) == 9
    assert not any("final-verifier" in op["path"] for op in plan["operations"])
    explorer_operations = [op for op in plan["operations"] if "agents/sdd-explorer." in op["path"]]
    assert len(explorer_operations) == 1
    assert plan["operations"][-1]["path"] == ".sdd/settings.json"
    result = core.apply_plan(plan)
    assert len(result["changed"]) == 9
    shared, _ = core.shared_contract()
    roles, _, _ = shared.settings(project)
    assert set(roles) == set(shared.ROLES)
    for row in view["roles"]:
        suffix = ".codex/agents/" + row["default"] + ".toml" if host == "codex" else ".claude/agents/" + row["default"] + ".md"
        data, body = core.parse_agent((project / suffix).read_bytes(), host, suffix)
        expected_model = row["profile_default"]["model"]
        assert data.get("model") == ("inherit" if host == "claude-code" and expected_model is None else expected_model)
        assert data.get("model_reasoning_effort" if host == "codex" else "effort") == row["profile_default"]["effort"]
        assert data["name"] == row["default"]
        if host == "codex":
            selection = shared.resolve(project, row["role"], host, "parent", "low", user_agent_dir=tmp_path / "user")
            assert selection["launch"]["model"] == (expected_model or "parent")
            assert selection["launch"]["reasoning_effort"] == (row["profile_default"]["effort"] or "low")
        else:
            assert body.strip() == core.INSTRUCTIONS
    no_change = core.make_plan(keep(inspect(tmp_path, host)))
    assert no_change["operations"] == []
    assert core.apply_plan(no_change)["changed"] == []
    assert not (project / ".sdd/.setup.lock").exists()


def test_presets_names_are_portable_and_models_differ(tmp_path):
    codex = inspect(tmp_path)
    claude = inspect(tmp_path, "claude-code")
    assert [r["default"] for r in codex["roles"]] == [r["default"] for r in claude["roles"]]
    for view in (codex, claude):
        assert len({r["profile_default"]["model"] for r in view["roles"]}) > 1
        assert all(r["profile_default"]["model"] != "inherit" for r in view["roles"])


def test_settings_extras_preserved_and_named_missing_created(tmp_path):
    view = inspect(tmp_path, names=["team-coder"])
    project = Path(view["project_root"])
    write(project / ".sdd/settings.json", json.dumps({"schema_version": 1, "team": {"name": "core"},
        "subagents": {"roles": {"sdd-apply.executor": "team-coder"}}}))
    view = inspect(tmp_path, names=["team-coder"])
    request = defaults(view)
    request["roles"]["sdd-apply.executor"] = {"action": "keep"}
    request["agents"]["team-coder"] = request["agents"].pop("sdd-executor")
    core.apply_plan(core.make_plan(request))
    assert core.read_json(project / ".sdd/settings.json")["team"] == {"name": "core"}
    assert (project / ".codex/agents/team-coder.toml").is_file()
    # Extend the existing setup fixture: split explorer selections and preserve
    # the shared profile and unrelated configuration without another real scenario.
    before = (project / ".codex/agents/sdd-explorer.toml").read_bytes()
    request = keep(inspect(tmp_path, names=["researcher", "checker"]))
    request["roles"]["sdd-spec.explorer"] = {"action": "set", "value": "researcher"}
    request["roles"]["sdd-apply.explorer"] = {"action": "set", "value": "checker"}
    request["agents"].pop("sdd-explorer")
    for name, model in (("researcher", "research-model"), ("checker", "check-model")):
        request["agents"][name] = {"model": {"action": "set", "value": model},
                                   "effort": {"action": "set", "value": "medium"}}
    snapshot = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    plan = core.make_plan(request)
    assert snapshot == {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    core.apply_plan(plan)
    settings = core.read_json(project / ".sdd/settings.json")
    assert settings["subagents"]["roles"]["sdd-spec.explorer"] == "researcher"
    assert settings["subagents"]["roles"]["sdd-apply.explorer"] == "checker"
    assert settings["team"] == {"name": "core"}
    assert (project / ".codex/agents/sdd-explorer.toml").read_bytes() == before
    shared, _ = core.shared_contract()
    for role, model in (("sdd-spec.explorer", "research-model"), ("sdd-apply.explorer", "check-model")):
        selected = shared.resolve(project, role, "codex", "parent", "low", user_agent_dir=tmp_path / "user")
        assert selected["launch"] == {"fork_turns": "none", "model": model, "reasoning_effort": "medium"}


@pytest.mark.parametrize("host", ["codex", "claude-code"])
def test_update_preserves_comments_and_custom_behavior(tmp_path, host):
    view = inspect(tmp_path, host)
    core.apply_plan(core.make_plan(defaults(view)))
    project = Path(view["project_root"])
    path = project / (".codex/agents/sdd-executor.toml" if host == "codex" else ".claude/agents/sdd-executor.md")
    if host == "codex":
        original = '# team comment\n' + path.read_text() + '\n[features]\nshell_tool = false\n'
    else:
        original = path.read_text().replace("description:", "# team comment\ntools: Read, Grep\ndescription:") + "\nCustom instruction.\n"
    write(path, original)
    request = keep(inspect(tmp_path, host))
    request["agents"]["sdd-executor"]["model"] = {"action": "set", "value": "custom-model"}
    core.apply_plan(core.make_plan(request))
    updated = path.read_text()
    assert "# team comment" in updated
    assert "shell_tool = false" in updated if host == "codex" else "Custom instruction." in updated and "tools: Read, Grep" in updated
    assert "custom-model" in updated


def test_missing_fields_require_choice_and_explicit_inherit_preserves_bytes(tmp_path):
    view = inspect(tmp_path)
    project = Path(view["project_root"])
    write(project / ".codex/agents/sdd-executor.toml", core.render_agent(None, "codex", "sdd-executor", None, None))
    request = defaults(inspect(tmp_path))
    request["agents"]["sdd-executor"] = {"model": {"action": "keep"}, "effort": {"action": "keep"}}
    with pytest.raises(ValueError, match="unset"):
        core.make_plan(request)
    request["agents"]["sdd-executor"] = {"model": {"action": "set", "value": None}, "effort": {"action": "set", "value": None}}
    plan = core.make_plan(request)
    assert not any(op["path"].endswith("sdd-executor.toml") for op in plan["operations"])


@pytest.mark.parametrize("host", ["codex", "claude-code"])
def test_user_agent_changes_create_project_override(tmp_path, host):
    view = inspect(tmp_path, host)
    suffix = ".toml" if host == "codex" else ".md"
    personal = tmp_path / "user" / ("sdd-executor" + suffix)
    write(personal, core.render_agent(None, host, "sdd-executor", "personal-model", "low"))
    before = personal.read_bytes()
    request = defaults(inspect(tmp_path, host))
    plan = core.make_plan(request)
    assert any("project override" in w for w in plan["warnings"])
    core.apply_plan(plan)
    assert personal.read_bytes() == before


def test_claude_live_native_name_is_not_recreated(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    view = core.inspect_project(project, "claude-code", user_agent_dir=tmp_path / "user",
                                available_agents=["general-purpose", "sdd-executor"])
    request = defaults(view)
    request["agents"]["sdd-executor"] = {"model": {"action": "keep"}, "effort": {"action": "keep"}}
    plan = core.make_plan(request)
    assert not any(op["path"].endswith("sdd-executor.md") for op in plan["operations"])
    request["agents"]["sdd-executor"]["model"] = {"action": "default"}
    with pytest.raises(ValueError, match="host-managed"):
        core.make_plan(request)


def test_shared_agent_conflicting_defaults_need_explicit_profile(tmp_path):
    view = inspect(tmp_path, names=["shared"])
    request = defaults(view)
    request["roles"] = {r["role"]: {"action": "set", "value": "shared"} for r in view["roles"]}
    request["agents"] = {"shared": {"model": {"action": "default"}, "effort": {"action": "default"}}}
    with pytest.raises(ValueError, match="different presets"):
        core.make_plan(request)
    request["agents"]["shared"] = {"model": {"action": "set", "value": "chosen-model"}, "effort": {"action": "set", "value": "high"}}
    plan = core.make_plan(request)
    assert len(plan["operations"]) == 2


def test_explicit_inheritance_omits_role_and_native_model(tmp_path):
    request = defaults(inspect(tmp_path))
    request["roles"]["sdd-spec.editor"] = {"action": "set", "value": None}
    request["agents"].pop("sdd-editor")
    request["agents"]["sdd-executor"] = {"model": {"action": "set", "value": None}, "effort": {"action": "set", "value": None}}
    plan = core.make_plan(request)
    assert "sdd-spec.editor" not in plan["selected_roles"]
    executor = next(o for o in plan["operations"] if o["path"].endswith("sdd-executor.toml"))
    assert "model =" not in executor["after"]


@pytest.mark.parametrize("change", ["settings", "catalog", "tamper", "role_missing", "agent_missing", "missing_keep", "name_not_inspected"])
def test_invalid_or_stale_decisions_cannot_write(tmp_path, change):
    request = defaults(inspect(tmp_path))
    project = Path(request["inspection"]["project_root"])
    plan = core.make_plan(request)
    if change == "settings":
        write(project / ".sdd/settings.json", '{"schema_version":1,"team":"changed"}')
    elif change == "catalog":
        write(project / ".codex/agents/new.toml", core.render_agent(None, "codex", "new", None, None))
    elif change == "tamper":
        plan["operations"][0]["after"] += "# forged\n"
    elif change == "role_missing":
        del request["roles"]["sdd-spec.editor"]
    elif change == "agent_missing":
        del request["agents"]["sdd-editor"]
    elif change == "missing_keep":
        request["agents"]["sdd-editor"]["model"] = {"action": "keep"}
    else:
        request["roles"]["sdd-spec.editor"] = {"action": "set", "value": "uninspected"}
        request["agents"]["uninspected"] = request["agents"].pop("sdd-editor")
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        if change in ("settings", "catalog", "tamper"):
            core.apply_plan(plan)
        else:
            core.make_plan(request)
    assert before == {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}


@pytest.mark.parametrize("text", ['{"schema_version":1,"schema_version":1}', '{"schema_version":9}',
                                  '{"schema_version":1,"subagents":{"roles":{"wrong":"agent"}}}'])
def test_malformed_settings_fail_without_repair(tmp_path, text):
    view = inspect(tmp_path)
    path = Path(view["project_root"]) / ".sdd/settings.json"
    write(path, text)
    with pytest.raises(ValueError):
        inspect(tmp_path)
    assert path.read_text() == text


def test_lock_prevents_overlapping_setup(tmp_path):
    plan = core.make_plan(defaults(inspect(tmp_path)))
    project = Path(plan["request"]["inspection"]["project_root"])
    write(project / ".sdd/.setup.lock", "another process")
    with pytest.raises(ValueError, match="Another setup"):
        core.apply_plan(plan)
    assert (project / ".sdd/.setup.lock").read_text() == "another process"
    assert not (project / ".codex").exists()


def test_mid_write_failure_rolls_back_exact_bytes(tmp_path, monkeypatch):
    view = inspect(tmp_path)
    core.apply_plan(core.make_plan(defaults(view)))
    project = Path(view["project_root"])
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    request = keep(inspect(tmp_path))
    for choice in request["agents"].values():
        choice["model"] = {"action": "set", "value": "new-model"}
    plan = core.make_plan(request)
    original = core.replace_file
    calls = 0
    def fail_once(path, raw):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected write failure")
        original(path, raw)
    monkeypatch.setattr(core, "replace_file", fail_once)
    with pytest.raises(ValueError, match="rolled back"):
        core.apply_plan(plan)
    assert before == {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_escape_and_symlink_targets_rejected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(ValueError):
        core.safe_target(project, "../outside")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (project / ".sdd").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host cannot create symlinks")
    with pytest.raises(ValueError, match="escapes|Symlink"):
        core.safe_target(project, ".sdd/settings.json")


def test_cli_inspect_does_not_write_consumer(tmp_path):
    project = tmp_path / "consumer"
    project.mkdir()
    script = core.PACKAGE / "scripts/setup.py"
    result = subprocess.run([sys.executable, "-B", str(script), "inspect", "--project-root", str(project),
                             "--host", "codex", "--user-agent-dir", str(tmp_path / "user")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(json.loads(result.stdout)["result"]["roles"]) == 9
    assert not list(project.iterdir())


def test_switch_host_keeps_role_names_and_codex_bytes(tmp_path):
    codex = inspect(tmp_path)
    core.apply_plan(core.make_plan(defaults(codex)))
    project = Path(codex["project_root"])
    before = {p: p.read_bytes() for p in (project / ".codex").rglob("*") if p.is_file()}
    settings_before = (project / ".sdd/settings.json").read_bytes()
    claude = inspect(tmp_path, "claude-code")
    request = defaults(claude)
    request["roles"] = {r["role"]: {"action": "keep"} for r in claude["roles"]}
    core.apply_plan(core.make_plan(request))
    assert before == {p: p.read_bytes() for p in (project / ".codex").rglob("*") if p.is_file()}
    assert (project / ".sdd/settings.json").read_bytes() == settings_before
    assert len(list((project / ".claude/agents").glob("*.md"))) == 8


def test_unset_roles_cannot_silently_keep_inheritance(tmp_path):
    request = defaults(inspect(tmp_path))
    request["roles"]["sdd-spec.editor"] = {"action": "keep"}
    with pytest.raises(ValueError, match="missing"):
        core.make_plan(request)


def test_agent_symlink_inside_project_is_not_followed_for_writes(tmp_path):
    view = inspect(tmp_path)
    project = Path(view["project_root"])
    target = project / "unrelated.toml"
    write(target, core.render_agent(None, "codex", "sdd-executor", "custom-model", "low"))
    link = project / ".codex/agents/alias.toml"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Host cannot create symlinks")
    before = target.read_bytes()
    with pytest.raises(ValueError, match="Symlink"):
        core.make_plan(defaults(inspect(tmp_path)))
    assert target.read_bytes() == before


def test_invalid_agent_name_cannot_be_used_as_path(tmp_path):
    request = defaults(inspect(tmp_path, names=["../../escape"]))
    request["roles"]["sdd-spec.editor"] = {"action": "set", "value": "../../escape"}
    request["agents"]["../../escape"] = request["agents"].pop("sdd-editor")
    with pytest.raises(ValueError, match="New project agent names"):
        core.make_plan(request)


def test_duplicate_agent_names_and_bad_toml_fail(tmp_path):
    view = inspect(tmp_path)
    project = Path(view["project_root"])
    raw = core.render_agent(None, "codex", "sdd-executor", "model", "high")
    write(project / ".codex/agents/one.toml", raw)
    write(project / ".codex/agents/two.toml", raw)
    with pytest.raises(ValueError, match="Duplicate agent"):
        inspect(tmp_path)
    write(project / ".codex/agents/two.toml", "not valid toml")
    with pytest.raises(ValueError):
        inspect(tmp_path)
