"""Audit decisions use fake process/filesystem adapters; no mise installation or network."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import project_audit
import setup as setup_cli


@pytest.fixture
def process(monkeypatch):
    executable = str(Path("mise installation") / "mise.exe")
    monkeypatch.setattr(project_audit.shutil, "which", Mock(return_value=executable))
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="2026.11.8 windows-x64\n", stderr=""))
    monkeypatch.setattr(project_audit.subprocess, "run", run)
    return run


def test_mise_not_on_path_is_not_proof_of_absent_installation(monkeypatch, process):
    monkeypatch.setattr(project_audit.shutil, "which", Mock(return_value=None))
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


def test_existing_absolute_path_does_not_require_path_changes(process):
    executable = str(Path("existing mise").absolute() / "mise.exe")
    row = project_audit.check_mise("project", executable)
    assert row["status"] == "satisfied" and row["executable"] == executable
    project_audit.shutil.which.assert_not_called()


@pytest.mark.parametrize("path", ["relative/mise", ""])
def test_explicit_path_must_be_absolute(process, path):
    with pytest.raises(ValueError, match="absolute path"):
        project_audit.check_mise("project", path)
    process.assert_not_called()


@pytest.mark.parametrize("suffix", [".cmd", ".bat"])
def test_batch_wrappers_are_not_executed(process, suffix):
    row = project_audit.check_mise("project", str(Path("mise" + suffix).absolute()))
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
    result = project_audit.audit_project("project", "mise-path")
    check.assert_called_once_with(project, "mise-path")
    assert result["project_root"] == "resolved-project"
    assert result["requirements"] == [row] and result["compliant"] is compliant
    assert result["checked_at"] and result["system"]


def test_invalid_project_is_not_reported_as_compliant(monkeypatch):
    project = Mock(is_dir=Mock(return_value=False))
    monkeypatch.setattr(project_audit, "Path", Mock(return_value=Mock(resolve=Mock(return_value=project))))
    with pytest.raises(ValueError, match="existing directory"):
        project_audit.audit_project("file")


@pytest.mark.parametrize("output", [False, True])
def test_cli_audit_needs_no_host_and_distinguishes_execution_from_compliance(monkeypatch, capsys, output):
    audit = Mock(return_value={"compliant": False, "requirements": [{"id": "mise", "status": "not_found"}]})
    monkeypatch.setattr(setup_cli, "audit_project", audit)
    for name in ("inspect_project", "make_plan", "apply_plan"):
        monkeypatch.setattr(setup_cli, name, Mock(side_effect=AssertionError("Role setup must not run")))
    saved = Mock(return_value={"summary": audit.return_value, "output_file": "audit.json"})
    monkeypatch.setattr(setup_cli, "save_result", saved)
    args = ["setup.py", "audit", "--project-root", "project", "--mise-path", "mise-path"]
    monkeypatch.setattr(setup_cli.sys, "argv", args + (["--output", "audit.json"] if output else []))
    assert setup_cli.main() == 0
    audit.assert_called_once_with(project_root="project", mise_path="mise-path")
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    if output:
        saved.assert_called_once_with(audit.return_value, Path("audit.json"), "audit")
        assert body["result"]["summary"]["compliant"] is False
    else:
        saved.assert_not_called()
        assert body["result"]["compliant"] is False
