"""Normal uv entry points from copied installs and conflicting consumers."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from lib.common import digest

ROOT = Path(__file__).resolve().parents[1]


def invoke(script, cwd, *args, env=None):
    return subprocess.run(["uv", "run", "--locked", "--script", str(script), *args], cwd=cwd, env=env, capture_output=True, timeout=120)


@pytest.mark.parametrize("installed", [False, True])
@pytest.mark.parametrize("conflict", [False, True])
def test_source_and_installed_entrypoints(tmp_path, installed, conflict):
    package = tmp_path / "installed/sdd-apply" if installed else ROOT
    if installed:
        shutil.copytree(ROOT, package)
    cwd = tmp_path / "consumer"
    cwd.mkdir()
    if conflict:
        (cwd / "pyproject.toml").write_text('[project]\nname="conflict"\nversion="0.0.0"\nrequires-python=">=3.11"\ndependencies=["pytest==0.0.1"]\n')
    before = {p.name: p.read_bytes() for p in cwd.iterdir()}
    locks = {p: p.read_bytes() for p in (package / "scripts").glob("*.lock")}
    for repeat in range(2):
        result = invoke(package / "scripts/execute.py", cwd, "--help")
        assert result.returncode == 0, result.stderr
        result = invoke(package / "scripts/test.py", cwd, "tests/test_package.py", "-q")
        assert result.returncode == 0, result.stdout + result.stderr
    assert before == {p.name: p.read_bytes() for p in cwd.iterdir()}
    assert locks == {p: p.read_bytes() for p in locks}
    assert not list(package.rglob("*.pyc"))
    assert not [p for p in package.rglob("*") if p.name in {".venv", ".pytest_cache", "__pycache__"}]


def test_offline_empty_cache_and_stale_lock(tmp_path):
    package = tmp_path / "copy"
    shutil.copytree(ROOT, package)
    env = {**os.environ, "UV_CACHE_DIR": str(tmp_path / "empty-cache")}
    script = package / "scripts/execute.py"
    result = subprocess.run(["uv", "run", "--offline", "--locked", "--script", str(script), "--help"], env=env, capture_output=True, timeout=60)
    assert result.returncode != 0 and (b"offline" in result.stderr.lower() or b"network connectivity is disabled" in result.stderr.lower())
    lock = script.with_suffix(".py.lock")
    original = lock.read_bytes()
    script.write_text(script.read_text().replace("PyYAML==6.0.3", "PyYAML==6.0.2"))
    result = subprocess.run(["uv", "run", "--offline", "--locked", "--script", str(script), "--help"], capture_output=True, timeout=60)
    assert result.returncode != 0
    assert lock.read_bytes() == original


def test_first_run_and_cache_restoration(tmp_path):
    cache = (tmp_path / "owned-uv-cache").resolve()
    package = tmp_path / "installed/sdd-apply"
    shutil.copytree(ROOT, package)
    cwd = tmp_path / "unrelated"
    cwd.mkdir()
    env = {**os.environ, "UV_CACHE_DIR": str(cache)}
    hashes = {p: digest(p.read_bytes()) for p in package.rglob("*") if p.is_file()}
    for iteration in range(2):
        for script, args in (("execute.py", ["--help"]), ("test.py", ["tests/test_package.py", "-q"])):
            result = invoke(package / "scripts" / script, cwd, *args, env=env)
            assert result.returncode == 0, result.stdout + result.stderr
        if iteration == 0:
            assert cache.is_relative_to(tmp_path.resolve()) and cache.name == "owned-uv-cache"
            shutil.rmtree(cache)
    assert hashes == {p: digest(p.read_bytes()) for p in package.rglob("*") if p.is_file()}
    assert list(cwd.iterdir()) == []
