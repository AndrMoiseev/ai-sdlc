"""The launcher keeps runtime state out of distributable skill packages."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import run


def configure_cache(monkeypatch, base):
    monkeypatch.setenv("LOCALAPPDATA", str(base))
    monkeypatch.setenv("XDG_CACHE_HOME", str(base))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: base))


def test_copies_have_distinct_external_environments(tmp_path, monkeypatch):
    configure_cache(monkeypatch, tmp_path / "user cache")
    source = tmp_path / "repo/skills/sdd-spec"
    installed = tmp_path / "repo/.agents/skills/sdd-spec"
    assert run.cache_directory(source) != run.cache_directory(installed)
    assert not run.cache_directory(source).is_relative_to(source.parent)


def test_reject_cache_inside_skills(tmp_path, monkeypatch):
    skill = tmp_path / "skills/sdd-spec"
    configure_cache(monkeypatch, skill / "cache")
    with pytest.raises(ValueError, match="outside"):
        run.cache_directory(skill)


def test_launcher_routes_state_and_preserves_arguments(tmp_path, monkeypatch):
    configure_cache(monkeypatch, tmp_path / "cache with spaces")
    monkeypatch.setattr(run, "SKILL_ROOT", tmp_path / "skill with spaces")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "unrelated-environment")
    calls = []

    def execute(command, *, env):
        calls.append((command, env))
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(run.subprocess, "run", execute)
    assert run.main(["check", "--project-root", "project with spaces", "--stage", "documents"]) == 7
    command, env = calls.pop()
    assert command[-4:] == ["--project-root", "project with spaces", "--stage", "documents"]
    assert str(run.SKILL_ROOT / "scripts/check.py") in command
    cache = run.cache_directory(run.SKILL_ROOT)
    assert env["UV_PROJECT_ENVIRONMENT"] == str(cache / "venv")
    assert env["PYTHONPYCACHEPREFIX"] == str(cache / "pycache")
    assert env["UV_CACHE_DIR"] == str(cache.parent / "uv")
    assert os.environ["UV_PROJECT_ENVIRONMENT"] == "unrelated-environment"
    assert run.main(["test", "-q"]) == 7
    command, _ = calls.pop()
    assert f"cache_dir={cache / 'pytest'}" in command
    assert str(run.SKILL_ROOT / "tests") in command
    assert command[-1] == "-q"


def test_cache_dir_does_not_create_environment(tmp_path, monkeypatch, capsys):
    configure_cache(monkeypatch, tmp_path / "cache")
    monkeypatch.setattr(run, "SKILL_ROOT", tmp_path / "skill")
    assert run.main(["cache-dir"]) == 0
    assert capsys.readouterr().out.strip() == str(run.cache_directory(run.SKILL_ROOT))
    assert not run.cache_directory(run.SKILL_ROOT).exists()
