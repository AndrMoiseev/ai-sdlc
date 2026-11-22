from configparser import ConfigParser
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML
import setup_core as core


def run_uv(script, cwd, cache, *flags):
    return subprocess.run(["uv", "run", "--locked", *flags, "--python", sys.executable,
                           "--script", str(script), "--help"], cwd=cwd,
                          env=dict(os.environ, UV_CACHE_DIR=str(cache)), capture_output=True, text=True, timeout=90)


def installed_copy(tmp_path):
    installed = tmp_path / "installed packages" / "sdd-setup"
    shutil.copytree(core.PACKAGE, installed)
    companion = tmp_path / "installed packages" / "sdd-shared"
    shutil.copytree(core.PACKAGE.parent / "sdd-shared", companion)
    consumer = tmp_path / "consumer with spaces"
    consumer.mkdir()
    return installed, consumer


def test_runtime_metadata_locks_and_clean_package():
    for script in ("setup.py", "test.py"):
        path = core.PACKAGE / "scripts" / script
        text = path.read_text()
        assert "# /// script" in text and "# dependencies =" in text
        assert "sys.dont_write_bytecode = True" in text
        assert path.with_suffix(".py.lock").is_file()
    names = {p.name for p in core.PACKAGE.rglob("*")}
    assert not names & {"__pycache__", ".pytest_cache", ".venv", "node_modules"}
    assert not any(p.suffix == ".pyc" for p in core.PACKAGE.rglob("*"))


@pytest.mark.parametrize("major", [1, 2])
def test_detekt_delegates_overlapping_checks_to_ktlint(major):
    assets = core.PACKAGE / "assets"
    yaml = YAML(typ="safe")
    common = yaml.load(assets / "detekt.yml")
    version = yaml.load(assets / f"detekt-{major}.yml")
    style = common["style"] | version["style"]
    unused_import = "UnusedImports" if major == 1 else "UnusedImport"
    for rule in (unused_import, "ModifierOrder", "NewLineAtEndOfFile", "ExpressionBodySyntax",
                 "BracesOnIfStatements", "BracesOnWhenStatements", "MandatoryBracesLoops",
                 "NoTabs", "TrailingWhitespace", "OptionalUnit", "MaxLineLength"):
        assert style[rule]["active"] is False, rule
    assert common["empty-blocks"]["EmptyClassBlock"]["active"] is False
    assert style["WildcardImport"]["active"] is True


def test_missing_companion_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="matching sdd-shared"):
        core.shared_contract(tmp_path)


def test_ktlint_autocorrections_preserve_explicit_unit():
    profile = ConfigParser(interpolation=None)
    profile.read(core.PACKAGE / "assets" / "ktlint-1.8.0.editorconfig", encoding="utf-8")
    assert profile.sections() == ["*.{kt,kts}"]
    kotlin = profile["*.{kt,kts}"]
    assert kotlin["ktlint_code_style"] == "ktlint_official"
    assert kotlin["ktlint_standard"] == kotlin["ktlint_experimental"] == "disabled"
    assert kotlin["indent_size"] == "4"
    assert kotlin["ktlint_standard_indent"] == kotlin["ktlint_standard_op-spacing"] == "enabled"
    for rule in ("expression-operand-wrapping", "function-expression-body", "if-else-bracing",
                 "multiline-if-else", "multiline-loop", "no-empty-class-body",
                 "no-single-line-block-comment", "no-unused-imports", "string-template",
                 "unnecessary-parentheses-before-trailing-lambda", "when-entry-bracing"):
        assert kotlin[f"ktlint_standard_{rule}"] == "enabled", rule
    assert kotlin["ktlint_standard_no-unit-return"] == "disabled"
    assert kotlin.get("ktlint_standard_class-naming", "disabled") == "disabled"
    assert kotlin["ktlint_standard_max-line-length"] == "enabled"
    assert kotlin["max_line_length"] == "140"
    assert kotlin["ktlint_ignore_back_ticked_identifier"] == "false"


def test_empty_offline_cache_fails_without_project_changes(tmp_path):
    installed, consumer = installed_copy(tmp_path)
    result = run_uv(installed / "scripts/setup.py", consumer, tmp_path / "empty-cache", "--offline")
    assert result.returncode != 0
    assert "offline" in result.stderr.lower() or "cache" in result.stderr.lower()
    assert not list(consumer.iterdir())


def test_stale_lock_fails_without_rewrite(tmp_path):
    installed, consumer = installed_copy(tmp_path)
    script = installed / "scripts/setup.py"
    lock = script.with_suffix(".py.lock")
    before = lock.read_bytes()
    script.write_text(script.read_text().replace('>=3.11', '>=3.11.1'))
    # A locked run can install from wheel URLs without caching registry metadata.
    # Permit resolution here so an offline cache miss cannot mask the lock error.
    result = subprocess.run(["uv", "run", "--locked", "--python", sys.executable,
                             "--script", str(script), "--help"], cwd=consumer,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "lock" in result.stderr.lower()
    assert lock.read_bytes() == before
    assert not list(consumer.iterdir())


@pytest.mark.skipif(os.environ.get("SDD_SETUP_RUNTIME_TESTS") != "1", reason="Enable SDD_SETUP_RUNTIME_TESTS=1 for fresh online uv cache test")
def test_first_run_cached_run_relocation_and_conflicting_consumer(tmp_path):
    installed, consumer = installed_copy(tmp_path)
    before = {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    cache = tmp_path / "new-online-cache"
    # Source and installed script each get their own environment in external cache.
    for script in (core.PACKAGE / "scripts/setup.py", installed / "scripts/setup.py"):
        result = run_uv(script, consumer, cache)
        assert result.returncode == 0, result.stderr
        assert not list(consumer.iterdir())
    pyproject = consumer / "pyproject.toml"
    text = '[project]\nname="conflict"\nversion="1.0"\nrequires-python=">=3.11"\ndependencies=["nonexistent-sdd-fixture==0"]\n'
    pyproject.write_text(text)
    for _ in range(2):
        result = run_uv(installed / "scripts/setup.py", consumer, cache, "--offline")
        assert result.returncode == 0, result.stderr
    assert pyproject.read_text() == text
    assert list(consumer.iterdir()) == [pyproject]
    assert before == {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
