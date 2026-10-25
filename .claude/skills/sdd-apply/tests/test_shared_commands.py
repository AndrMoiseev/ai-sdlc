"""The process-free test adapter must agree with the shipped uv CLI."""
from pathlib import Path
import sys
import subprocess
import os

import pytest

from lib.common import Rejected
from shared_commands import spec_call

SHARED = Path(__file__).resolve().parents[2] / "sdd-shared"


@pytest.fixture
def process_cli(shared_cli, monkeypatch):
    """Check the actual CLI in the already locked Python environment."""
    run = subprocess.run
    def direct(command, **kwargs):
        assert command[:4] == ["uv", "run", "--locked", "--script"]
        return run([sys.executable, "-B", *command[4:]], **kwargs)
    def call(*args):
        with monkeypatch.context() as patch:
            patch.setattr("lib.inputs.subprocess.run", direct)
            return shared_cli(*args)
    return call


@pytest.mark.parametrize("stage,script", [
    ("documents", "check.py"), ("plan", "check.py"), ("plan", "snapshot.py"),
])
def test_shared_adapter_matches_real_cli(project, process_cli, stage, script):
    assert spec_call(SHARED, project, "demo", stage, script) == process_cli(SHARED, project, "demo", stage, script)


@pytest.mark.parametrize("damage", ["missing", "syntax"])
def test_shared_adapter_matches_real_cli_errors(project, process_cli, damage):
    root = project / "sdd/changes/demo"
    if damage == "missing":
        (root / "tasks.md").unlink()
    else:
        (root / "tasks.md").write_text("---\ninvalid: [\n---\n")
    with pytest.raises(Rejected) as expected:
        process_cli(SHARED, project, "demo", "plan", "check.py")
    with pytest.raises(Rejected) as actual:
        spec_call(SHARED, project, "demo", "plan", "check.py")
    assert actual.value.code == expected.value.code
    assert str(actual.value) == str(expected.value)


def test_shared_adapter_matches_missing_approval_result(project, process_cli):
    (project / "sdd/changes/demo/review/decisions.md").unlink()
    actual = spec_call(SHARED, project, "demo", "plan", "check.py")
    assert not actual["approval_status"]["ready"]
    assert actual == process_cli(SHARED, project, "demo", "plan", "check.py")


def test_shared_adapter_restores_import_context(project):
    before = {name: module for name, module in sys.modules.items()
              if name == "sdd_shared" or name.startswith("sdd_shared.")}
    paths = sys.path[:]
    spec_call(SHARED, project, "demo", "plan", "snapshot.py")
    after = {name: module for name, module in sys.modules.items()
             if name == "sdd_shared" or name.startswith("sdd_shared.")}
    assert before == after and sys.path == paths


@pytest.mark.installation
def test_shared_adapter_matches_shipped_uv_entrypoint(project, shared_cli):
    assert spec_call(SHARED, project, "demo", "plan", "check.py") == shared_cli(SHARED, project, "demo", "plan", "check.py")


def test_parsed_documents_are_independent_and_exact_bytes_invalidate_the_cache(project):
    from shared_commands import spec_modules
    docs = spec_modules(SHARED)
    path = project / "sdd/changes/demo/specs/demo/spec.md"
    first = docs.read_document(path)
    first.records[1]["expected"] = "mutated returned object"
    assert docs.read_document(path).records[1]["expected"] == "Sum"
    before = path.stat()
    path.write_bytes(path.read_bytes().replace(b"expected: Sum", b"expected: New"))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert docs.read_document(path).records[1]["expected"] == "New"
