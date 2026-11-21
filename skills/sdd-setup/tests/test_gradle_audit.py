import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import gradle_audit as audit


@pytest.mark.parametrize("properties,missing,status,version", [
    (r"distributionUrl=https\://mirror/gradle-8.9-bin.zip?token=secret", None, "configured", "8.9"),
    ("distributionUrl = ../dists/gradle-9.0.0-rc-1-all.zip", None, "configured", "9.0.0-rc-1"),
    ("distributionUrl=../custom.zip", None, "configured", None),
    ("distributionUrl= ", None, "incomplete", None),
    ("distributionUrl=../gradle-8.9-bin.zip", "gradle-wrapper.jar", "incomplete", None),
])
def test_wrapper_configuration(monkeypatch, properties, missing, status, version):
    monkeypatch.setattr(Path, "is_file", lambda path: path.name != missing)
    monkeypatch.setattr(Path, "stat", lambda path: SimpleNamespace(st_size=100))
    monkeypatch.setattr(Path, "read_text", lambda path, encoding: properties)
    monkeypatch.setattr(audit.os, "access", lambda *args: True)
    row = audit.gradle_wrapper(Path("project"))
    assert row["status"] == status and row.get("version") == version
    assert "secret" not in str(row)


@pytest.mark.parametrize("wrapper,mise,status", [
    (True, False, "satisfied"), (False, True, "satisfied"),
    (True, True, "satisfied"), (False, False, "failed"),
])
def test_either_project_installation_fulfils_requirement(monkeypatch, wrapper, mise, status):
    observation = {"status": "configured", "version": "8.9"} if wrapper else {"status": "not_found"}
    monkeypatch.setattr(audit, "gradle_wrapper", lambda project: observation)
    installed = Mock(side_effect=None if mise else ValueError("No project Gradle"))
    monkeypatch.setattr(audit, "check_tools", installed)
    release = Mock(return_value=io.BytesIO(b'{"current": true, "version": "8.10"}'))
    monkeypatch.setattr(audit, "urlopen", release)
    execute = Mock(side_effect=[b"gradle", b"8.10"])
    report = audit.check_gradle("project", execute)
    assert report["required"] and report["status"] == status
    assert release.called == (wrapper or mise)
    assert (report["evidence"]["mise"]["status"] == "configured") is mise
    installed.assert_called_once_with({"gradle": ["gradle"]}, "project", execute)
    assert report["evidence"]["wrapper"].get("suggested_version") == ("8.10" if wrapper else None)
    assert "suggested_version" not in report["evidence"]["mise"]


@pytest.mark.parametrize("current,stable,offer", [
    ("8.10", "8.9", False), ("9.0", "9.0.0", False), ("9.0.0", "9.0", False),
    ("9.0.0-rc-1", "9.0.0", True), ("9.1.0-milestone-2", "9.0.0", False),
    ("custom", "9.1.0", False),
])
def test_only_newer_versions_are_offered(current, stable, offer):
    assert audit.newer_stable(current, stable) is offer


@pytest.mark.parametrize("release", [
    {"version": "9.1.0-rc-1", "current": True}, {"version": "9.1", "current": True, "nightly": True},
    {"version": "9.1", "current": False}, OSError("offline"),
])
def test_release_lookup_failure_preserves_installed_wrapper(monkeypatch, release):
    response = Mock(side_effect=release) if isinstance(release, OSError) else Mock(
        return_value=io.BytesIO(json.dumps(release).encode()))
    monkeypatch.setattr(audit, "urlopen", response)
    monkeypatch.setattr(audit, "gradle_wrapper", lambda project: {"status": "configured", "version": "8.0"})
    report = audit.check_gradle("project", None)
    assert report["status"] == "satisfied" and report["release_error"]
    assert "suggested_version" not in report["evidence"]["wrapper"]
