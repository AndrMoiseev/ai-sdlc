"""Audit decisions use fake process/filesystem adapters; no mise installation or network."""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import project_audit
import setup as setup_cli


@pytest.fixture
def process(monkeypatch):
    executable = str(Path("mise installation").absolute() / "mise.exe")
    monkeypatch.setattr(project_audit, "find_mise_on_path", Mock(return_value=executable))
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="2026.11.8 windows-x64\n", stderr=""))
    monkeypatch.setattr(project_audit.subprocess, "run", run)
    return run


def test_mise_not_on_path_is_not_proof_of_absent_installation(monkeypatch, process):
    monkeypatch.setattr(project_audit, "find_mise_on_path", Mock(return_value=None))
    row = project_audit.check_mise("project")
    assert row["status"] == "not_found" and row["required"]
    assert row["executable"] is None and row["version"] is None
    assert "existing installation" in row["evidence"]["error"]
    process.assert_not_called()


def test_native_version_probe_keeps_arguments_and_has_a_deadline(process):
    row = project_audit.check_mise("project")
    assert row["status"] == "satisfied"
    assert row["version"] == "2026.11.8 windows-x64"
    assert row["evidence"]["returncode"] == 0
    process.assert_called_once_with(
        [row["executable"], "--version"], cwd="project", shell=False,
        stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", errors="replace", timeout=10,
    )


def test_existing_mise_requires_its_directory_on_path(monkeypatch):
    project = Path("project").absolute()
    filename = "mise.EXE" if os.name == "nt" else "mise"
    executable = project / filename
    monkeypatch.setenv("PATHEXT", ".EXE")
    monkeypatch.setattr(Path, "is_file", lambda path: path == executable)
    monkeypatch.setattr(os, "access", lambda path, mode: True)
    monkeypatch.setenv("PATH", str(project / "tools"))
    assert project_audit.find_mise_on_path(project) is None
    monkeypatch.setenv("PATH", str(project))
    assert project_audit.find_mise_on_path(project) == str(executable)


@pytest.mark.parametrize("suffix", [".cmd", ".bat"])
def test_batch_wrappers_are_not_executed(process, suffix):
    project_audit.find_mise_on_path.return_value = str(Path("mise" + suffix).absolute())
    row = project_audit.check_mise("project")
    assert row["status"] == "failed" and "native" in row["evidence"]["error"]
    process.assert_not_called()


@pytest.mark.parametrize("error,status", [
    (FileNotFoundError("executable disappeared"), "not_found"),
    (PermissionError("access denied"), "failed"),
    (OSError("invalid executable"), "failed"),
    (subprocess.TimeoutExpired(["mise", "--version"], 10), "failed"),
])
def test_probe_errors_remain_unsatisfied(process, error, status):
    process.side_effect = error
    row = project_audit.check_mise("project")
    assert row["status"] == status and row["version"] is None
    assert row["evidence"]["error"] == str(error)
    assert row["evidence"]["command"][-1] == "--version"


@pytest.mark.parametrize("code,stdout,stderr", [
    (1, "2026.11.8", "broken installation"),
    (0, "", ""),
    (0, "unrelated executable", ""),
])
def test_exit_status_and_version_both_matter(process, code, stdout, stderr):
    process.return_value = SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)
    row = project_audit.check_mise("project")
    assert row["status"] == "failed" and row["version"] is None
    assert row["evidence"]["stdout"] == stdout
    assert row["evidence"]["stderr"] == stderr
    assert row["evidence"]["returncode"] == code


@pytest.mark.parametrize("version", ["1.2.3", "2024.1.0", "mise 2026.11.8", "2026.11.8-dev.1 linux-x64"])
def test_requirement_does_not_invent_a_minimum_version(process, version):
    process.return_value.stdout = version + "\n"
    assert project_audit.check_mise("project")["status"] == "satisfied"


def test_repeat_probe_observes_repair_and_later_failure(process):
    process.side_effect = [
        PermissionError("access denied"), process.return_value,
        FileNotFoundError("removed"),
    ]
    assert [project_audit.check_mise("project")["status"] for _ in range(3)] == [
        "failed", "satisfied", "not_found",
    ]


@pytest.mark.parametrize("status,compliant", [("satisfied", True), ("not_found", False), ("failed", False)])
def test_audit_reports_compliance_from_observed_requirement(monkeypatch, status, compliant):
    project = MagicMock()
    project.is_dir.return_value = True
    project.__str__.return_value = "resolved-project"
    monkeypatch.setattr(project_audit, "Path", Mock(return_value=Mock(resolve=Mock(return_value=project))))
    row = {"id": "mise", "required": True, "status": status}
    check = Mock(return_value=row)
    monkeypatch.setattr(project_audit, "check_mise", check)
    result = project_audit.audit_project("project", None)
    check.assert_called_once_with(project)
    assert result["project_root"] == "resolved-project"
    assert result["requirements"] == [row] and result["compliant"] is compliant
    tools = result["recommended_tools"]
    assert {tool["binary"]: tool["tool_request"] for tool in tools} == {
        "uv": "uv@latest", "git": "conda:git@latest",
        "scc": "github:boyter/scc@latest", "rg": "ripgrep@latest",
        "node": "node@latest", "rga": "ripgrep-all@latest", "apm": "apm@latest",
    }
    for tool in tools:
        assert tool["use_command"] == ["mise", "use", "--path", "resolved-project", tool["tool_request"]]
    assert result["checked_at"] and result["system"]


def test_invalid_project_is_not_reported_as_compliant(monkeypatch):
    project = Mock(is_dir=Mock(return_value=False))
    monkeypatch.setattr(project_audit, "Path", Mock(return_value=Mock(resolve=Mock(return_value=project))))
    with pytest.raises(ValueError, match="existing directory"):
        project_audit.audit_project("file", None)


@pytest.mark.parametrize("requested,active,compiler,expected", [
    ("21", "temurin-21.0.3+9", "temurin-21.0.3+9", True),
    ("temurin-21.0.3+9", "temurin-21.0.3+9", "temurin-21.0.3+9", True),
    ("21.0.3", "21.0.30", "21.0.30", False),
    ("21", "17", "17", False),
    ("temurin-21", "zulu-21", "zulu-21", False),
    ("21", "21", "17", False),
])
def test_jvm_requires_project_jdk_and_matching_compiler(monkeypatch, requested, active, compiler, expected):
    mise = {"required": True, "status": "satisfied", "executable": "mise"}
    monkeypatch.setattr(project_audit, "check_mise", Mock(return_value=mise))
    gradle = {"id": "gradle", "required": True, "status": "satisfied"}
    monkeypatch.setattr(project_audit, "check_gradle", Mock(return_value=gradle))
    installed = Mock()
    monkeypatch.setattr(project_audit, "check_tools", installed)
    queries = [Mock(stdout=version.encode()) for version in (active, compiler)]
    monkeypatch.setattr(project_audit.subprocess, "run", Mock(side_effect=queries))
    project = MagicMock()
    project.is_dir.return_value = True
    monkeypatch.setattr(project_audit, "Path", Mock(return_value=Mock(resolve=Mock(return_value=project))))
    result = project_audit.audit_project("project", requested)
    java = result["requirements"][1]
    assert gradle in result["requirements"]
    assert installed.call_args.args[:2] == ({"java": ["java", "javac"]}, project)
    assert java["required"] and java["id"] == "java"
    assert result["compliant"] is expected
    assert java["use_command"][-1] == "java@" + requested


@pytest.mark.parametrize("version", ["", "latest", "temurin", "lts"])
def test_unresolved_java_has_no_install_action(monkeypatch, version):
    installed = Mock()
    monkeypatch.setattr(project_audit, "check_tools", installed)
    result = project_audit.check_java("project", Mock(), version)
    assert result["status"] == "failed" and "use_command" not in result
    installed.assert_not_called()


def test_missing_mise_or_jdk_blocks_java_verification(monkeypatch):
    installed = Mock(side_effect=ValueError("Configure and install java"))
    monkeypatch.setattr(project_audit, "check_tools", installed)
    assert project_audit.check_java("project", None, "21")["status"] == "failed"
    installed.assert_not_called()
    result = project_audit.check_java("project", Mock(), "21")
    assert result["evidence"]["error"] == "Configure and install java"
    assert result["status"] == "failed"


@pytest.mark.parametrize("output", [False, True])
def test_cli_audit_needs_no_host_and_distinguishes_execution_from_compliance(monkeypatch, capsys, output):
    audit = Mock(return_value={"compliant": False, "requirements": [{"id": "mise", "status": "not_found"}]})
    monkeypatch.setattr(setup_cli, "audit_project", audit)
    for name in ("inspect_project", "make_plan", "apply_plan"):
        monkeypatch.setattr(setup_cli, name, Mock(side_effect=AssertionError("Role setup must not run")))
    saved = Mock(return_value={"summary": audit.return_value, "output_file": "audit.json"})
    monkeypatch.setattr(setup_cli, "save_result", saved)
    args = ["setup.py", "audit", "--project-root", "project", "--jvm" if output else "--no-jvm"]
    monkeypatch.setattr(setup_cli.sys, "argv", args + (["--output", "audit.json"] if output else []))
    assert setup_cli.main() == 0
    audit.assert_called_once_with(project_root="project", java_version="" if output else None)
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    if output:
        saved.assert_called_once_with(audit.return_value, Path("audit.json"), "audit")
        assert body["result"]["summary"]["compliant"] is False
    else:
        saved.assert_not_called()
        assert body["result"]["compliant"] is False
