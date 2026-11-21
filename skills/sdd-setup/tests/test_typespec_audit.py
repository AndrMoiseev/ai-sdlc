from pathlib import Path
from unittest.mock import Mock

import pytest

import typespec_audit as audit


@pytest.mark.parametrize("declared,installed,pnp,status", [
    (False, False, False, "missing"), (True, False, False, "restore"),
    (False, True, False, "undeclared"), (True, True, False, "installed"),
    (True, False, True, "check_with_yarn"),
])
def test_inspect_workspace_uses_mise_node_and_project_compiler(monkeypatch, declared, installed, pnp, status):
    root = Path("repo").absolute()
    package = root / "api"
    node = root.parent / "mise" / "node"
    metadata = root / "node_modules" / audit.COMPILER / "package.json"
    files = {node: {}, package / "package.json": {"devDependencies": {audit.COMPILER: "^1.2"} if declared else {}}}
    if installed:
        files[metadata] = {"name": audit.COMPILER, "version": "1.2.3", "bin": {"tsp": "cmd/tsp.js"}}
    if pnp:
        files[root / ".pnp.cjs"] = {}
    monkeypatch.setattr(Path, "resolve", lambda path, strict=False: path)
    monkeypatch.setattr(Path, "is_dir", lambda path: path in (package, root))
    monkeypatch.setattr(Path, "is_file", lambda path: path in files)
    monkeypatch.setattr(audit, "read_json", files.__getitem__)
    monkeypatch.setattr(audit, "check_mise", Mock(return_value={"status": "satisfied"}))
    which = Mock(return_value=str(node).encode())
    monkeypatch.setattr(audit, "mise_reader", Mock(return_value=which))
    run = Mock(side_effect=[Mock(stdout="v24.0.0"), Mock(stdout="TypeSpec compiler v1.2.3")])
    monkeypatch.setattr(audit.subprocess, "run", run)
    result = audit.inspect_typespec(root, "api")
    assert result["status"] == status and result["node_version"] == "v24.0.0"
    which.assert_called_once_with(["mise", "which", "node"])
    assert ("declaration" in result) == declared
    if installed:
        assert result["version"] == "1.2.3"
        assert run.call_args.args[0] == [str(node), str(metadata.parent / "cmd/tsp.js"), "--version"]
    else:
        assert run.call_count == 1


def test_unavailable_mise_defers_compiler_check(monkeypatch):
    monkeypatch.setattr(audit, "check_mise", lambda _: {"status": "not_found", "evidence": {"error": "missing mise"}})
    run = Mock()
    monkeypatch.setattr(audit.subprocess, "run", run)
    result = audit.inspect_typespec(Path(__file__).parent)
    assert result["status"] == "node_unavailable" and result["error"] == "missing mise"
    run.assert_not_called()
