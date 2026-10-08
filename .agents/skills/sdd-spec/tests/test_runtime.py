"""Exercise the installed script contract through uv, outside a Python project."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SKILL = Path(__file__).resolve().parents[1]


@pytest.fixture
def installed(tmp_path):
    package = tmp_path / "installed skills" / "sdd-spec"
    shutil.copytree(SKILL, package, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".venv", ".pytest_cache", ".cache"))
    project = tmp_path / "consumer with spaces"
    project.mkdir()
    return package, project


def run_script(package, project, script, *args, env=None):
    return subprocess.run(
        ["uv", "run", "--locked", "--offline", "--python", sys.executable,
         "--script", str(package / "scripts" / script), *args],
        cwd=project, env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=60,
    )


@pytest.mark.parametrize("script", ["check.py", "snapshot.py"])
@pytest.mark.parametrize("conflicting_project", [False, True])
def test_relocated_script_ignores_consumer_dependencies(installed, script, conflicting_project):
    package, project = installed
    if conflicting_project:
        (project / "pyproject.toml").write_text(
            '[project]\nname = "consumer"\nversion = "1.0"\n'
            'requires-python = ">=3.11"\ndependencies = ["PyYAML==0.0.0"]\n',
            encoding="utf-8",
        )
    original = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    lockfile = package / "scripts" / (script + ".lock")
    locked = lockfile.read_bytes()
    # Missing SDD documents exercise dependency imports and structured errors.
    result = run_script(package, project, script, "--project-root", str(project),
                        "--change", "missing", "--stage", "documents")
    assert result.returncode in (1, 2), result.stderr
    assert "ModuleNotFoundError" not in result.stderr + result.stdout
    assert '"code": "environment"' not in result.stdout + result.stderr
    assert '"code":' in result.stdout + result.stderr, result.stderr
    assert lockfile.read_bytes() == locked
    assert not list(package.rglob("__pycache__"))
    assert not list(package.rglob("*.pyc"))
    assert not (package / ".venv").exists()
    assert not (project / ".venv").exists()
    assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()} == original


def test_stale_script_lock_fails_without_rewriting(installed):
    package, project = installed
    script = package / "scripts/check.py"
    script.write_text(script.read_text(encoding="utf-8").replace(
        '# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0"]',
        '# dependencies = []'), encoding="utf-8")
    lockfile = script.with_suffix(".py.lock")
    locked = lockfile.read_bytes()
    result = run_script(package, project, "check.py", "--help")
    assert result.returncode != 0
    assert "lock" in result.stderr.lower(), result.stderr
    assert lockfile.read_bytes() == locked


def test_empty_cache_fails_offline_without_touching_package(installed, tmp_path):
    package, project = installed
    env = dict(os.environ, UV_CACHE_DIR=str(tmp_path / "empty cache"))
    lockfile = package / "scripts/check.py.lock"
    locked = lockfile.read_bytes()
    result = run_script(package, project, "check.py", "--help", env=env)
    assert result.returncode != 0
    assert "offline" in result.stderr.lower() or "network" in result.stderr.lower(), result.stderr
    assert lockfile.read_bytes() == locked
    assert not list(package.rglob("__pycache__"))
