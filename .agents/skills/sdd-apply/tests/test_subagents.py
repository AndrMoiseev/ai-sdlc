"""Synthetic selection attestations; these tests do not launch real hosts."""
from lib import artifact_storage as artifacts
import json
from pathlib import Path
import pytest
from lib.api import dispatch
from lib.subagents import resolve


def settings(driver, roles):
    root = Path(driver.state["basis"]["project_root"])
    path = root / ".sdd/settings.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "subagents": {"roles": roles}}))
    return root


def register(driver, kind, ident, context, selection, lens_id="code"):
    return driver.send("role_register", {"role_id": ident, "kind": kind,
        "context_id": context, "fresh": True, "host": selection["host"],
        "launch_ref": "synthetic-selection-test", "capabilities": {"fresh_context": True},
        "agent_selection": selection, **({"lens_id": lens_id} if kind == "reviewer" else {})})


def selection(driver, kind, **kwargs):
    return resolve(driver.state, kind, host="codex", parent_model="parent", parent_effort="high", **kwargs)


def test_configured_registration_requires_selection(driver):
    settings(driver, {})
    with pytest.raises(ValueError, match="Resolve the role"):
        driver.role("author", "executor")
    selected = selection(driver, "executor")
    result = register(driver, "executor", "author", "ctx", selected)
    packet = json.loads(artifacts.read_text(result["packet"]))
    assert packet["role"]["agent_selection"] == selected


def test_review_lenses_require_distinct_contexts_even_with_matching_profiles(driver):
    settings(driver, {})
    selected = selection(driver, "reviewer")
    register(driver, "reviewer", "v", "ctx", selected, "verification")
    with pytest.raises(ValueError, match="every reviewer starts fresh"):
        register(driver, "reviewer", "r", "ctx", selected)
    register(driver, "reviewer", "r", "other-ctx", selected)
    assert len(driver.state["roles"]) == 2


def test_distinct_models_require_distinct_contexts(driver):
    root = settings(driver, {"sdd-apply.reviewer": "reviewer"})
    catalog = root / ".codex/agents"
    catalog.mkdir(parents=True)
    (catalog / "r.toml").write_text('name="reviewer"\ndescription="Review"\n'
        'developer_instructions="Review"\nmodel="other-model"\n')
    register(driver, "reviewer", "v", "ctx", selection(driver, "reviewer"), "verification")
    selected = selection(driver, "reviewer")
    with pytest.raises(ValueError, match="every reviewer starts fresh"):
        register(driver, "reviewer", "r", "ctx", selected)
    register(driver, "reviewer", "r2", "different", selected)


def test_wrong_role_attestation_rejected(driver):
    with pytest.raises(ValueError, match="another role"):
        register(driver, "executor", "x", "ctx", selection(driver, "reviewer"))


def test_api_uses_saved_project_root_not_worktree(driver, tmp_path, monkeypatch):
    settings(driver, {"sdd-apply.reviewer": "missing"})
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    monkeypatch.chdir(worktree)
    result = dispatch({"operation": "resolve_agent", "args": {"directory": str(driver.directory),
        "kind": "reviewer", "host": "codex", "parent_model": "parent"}})
    assert result["reason"] == "agent_missing"
    assert result["project_root"] == driver.state["basis"]["project_root"]


def test_existing_run_missing_sibling_has_actionable_error(driver, tmp_path, monkeypatch):
    import shared
    state = driver.state
    monkeypatch.setattr(shared, "__file__", str(tmp_path / "sdd-apply/scripts/shared.py"))
    with pytest.raises(ValueError, match="Critical dependency sdd-shared is missing"):
        resolve(state, "executor", host="codex", parent_model="parent")


def test_native_claude_definitions_do_not_share_context_from_name_only(driver):
    settings(driver, {"sdd-apply.reviewer": "native"})
    def native(kind):
        return resolve(driver.state, kind, host="claude-code", parent_model="parent",
                       available_agents=["native"])
    register(driver, "reviewer", "v", "ctx", native("reviewer"), "verification")
    with pytest.raises(ValueError, match="every reviewer starts fresh"):
        register(driver, "reviewer", "r", "ctx", native("reviewer"))


def test_forged_launch_fields_do_not_match_resolution(driver):
    selected = selection(driver, "executor")
    selected["launch"]["model"] = "unconfigured-model"
    with pytest.raises(ValueError, match="catalog or launch selection changed"):
        register(driver, "executor", "x", "ctx", selected)
