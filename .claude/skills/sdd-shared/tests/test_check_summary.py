"""Parser matrices use bytes and mappings; command execution contracts live in apply."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdd_shared import module
from sdd_shared.check_summary import aggregate, check_summary, junit_counts, report_specs


def output(**fields):
    return {"check_id": "suite", "command": ["pytest", "-q"], "cwd": "/work",
            "started_at": "2026-10-29T00:00:00+00:00", "duration_seconds": 2.5,
            "exit_code": 0, "outcome": "passed", "stdout": "", "stderr": "", **fields}


def test_shared_modules_are_public_without_version_change():
    import sdd_shared
    assert sdd_shared.API_VERSION == 2
    assert module("explorer").validate_assignment
    assert module("check_runner").run_command
    assert module("check_summary").check_summary is check_summary


def test_runner_preserves_raw_bytes_and_exact_process_options(monkeypatch):
    import base64
    runner = module("check_runner")
    command = ["tool", "literal ; argument"]
    observed = {}
    class Process:
        returncode = 7
        def communicate(self, timeout):
            assert timeout == 5
            return b"raw\xff", b"failure"
    def start(args, **options):
        observed.update(args=args, **options)
        return Process()
    monkeypatch.setattr(runner.subprocess, "Popen", start)
    result = runner.run_command(command, "/work", 5)
    assert observed["args"] == command and observed["shell"] is False
    assert observed["cwd"] == "/work"
    assert base64.b64decode(result["stdout_base64"]) == b"raw\xff"
    assert result["stdout"] == "raw\ufffd"
    assert result["exit_code"] == 7 and result["outcome"] == "failed"


@pytest.mark.parametrize("fields", [
    {}, {"exit_code": 7, "outcome": "failed", "stderr": "failure"},
    {"exit_code": None, "outcome": "unavailable", "limitation": "timeout"},
])
def test_generic_metadata_counts_and_diagnosis_cannot_invent_success(fields):
    raw = output(**fields)
    raw["diagnosis"] = "All tests passed"
    before = deepcopy(raw)
    result = check_summary(raw, {"stage": "self", "configuration": {"path": "config"}}, {})
    for key in ("command", "cwd", "started_at", "duration_seconds", "exit_code", "outcome"):
        assert result[key] == raw[key]
    assert all(result["test_counts"][key] is None for key in result["test_counts"]["unknown_fields"])
    assert len(result["test_counts"]["unknown_fields"]) == 6
    assert result["configuration"] == {"path": "config"}
    assert "diagnosis" not in result
    assert raw == before


@pytest.mark.parametrize("size", [0, 4095, 4096, 4097, 15000])
def test_excerpt_has_exact_bound_offset_and_reference(size):
    text = ("line\n" * (size // 5 + 1))[:size]
    result = check_summary(output(stderr=text, exit_code=1, outcome="failed"), {}, {"stderr": "raw-ref"})
    excerpt = result["excerpt"]
    assert len(excerpt["text"]) == min(size, 4096)
    assert excerpt["offset"] == max(size - 4096, 0)
    assert excerpt["line"] == text.count("\n", 0, excerpt["offset"]) + 1
    assert excerpt["truncated"] is (size > 4096)
    if size:
        assert excerpt["reference"] == "raw-ref"
        assert excerpt["text"] == text[excerpt["offset"]:]
    assert result["outcome"] == "failed"


def test_eight_skips_at_exit_zero_remain_visible():
    raw = b'<testsuites><testsuite tests="9" skipped="8"><testcase/>' + b'<testcase><skipped/></testcase>' * 8 + b'</testsuite></testsuites>'
    counts = junit_counts(raw)
    assert counts == {"collected": None, "passed": 1, "failed": 0, "skipped": 8,
                      "xfailed": 0, "xpassed": None, "unknown_fields": ["collected", "xpassed"]}
    result = check_summary(output(), {}, {}, [{"format": "pytest-junit", "path": "report.xml",
                          "required": True, "test_counts": counts}])
    assert result["exit_code"] == 0 and result["outcome"] == "passed"
    assert result["test_counts"]["skipped"] == 8


def test_junit_failure_error_and_xfail_are_observed_without_inventing_xpass():
    raw = b'<testsuite tests="4" failures="1" errors="1" skipped="1"><testcase/><testcase><failure/></testcase><testcase><error/></testcase><testcase><skipped type="pytest.xfail"/></testcase></testsuite>'
    counts = junit_counts(raw)
    assert (counts["passed"], counts["failed"], counts["skipped"], counts["xfailed"]) == (1, 2, 0, 1)
    assert counts["xpassed"] is None and counts["collected"] is None


@pytest.mark.parametrize("raw", [b"broken", b"<report/>", b"<testsuites/>",
    b'<testsuite tests="2"><testcase/></testsuite>', b'<testsuite tests="-1"/>',
    b'<!DOCTYPE testsuite><testsuite tests="0"/>'])
def test_damaged_junit_is_an_error(raw):
    with pytest.raises(ValueError):
        junit_counts(raw)


@pytest.mark.parametrize("required", [True, False])
def test_missing_or_invalid_report_keeps_exit_and_marks_evidence(required):
    result = check_summary(output(), {}, {}, [{"format": "pytest-junit", "path": "report.xml",
                          "required": required, "error": "Invalid JUnit XML"}])
    assert result["exit_code"] == 0 and result["outcome"] == "passed"
    assert result["evidence_complete"] is not required
    assert result["limitations"] == [{"report": "report.xml", "reason": "Invalid JUnit XML"}]
    assert result["test_counts"]["skipped"] is None


@pytest.mark.parametrize("flag", [["--junitxml", "report.xml"], ["--junit-xml=report.xml"]])
def test_report_discovery_preserves_exact_command(flag):
    command = ["pytest", "-q", *flag]
    original = command[:]
    assert report_specs(command, {}) == [{"format": "pytest-junit", "path": "report.xml", "required": True}]
    assert command == original
    assert report_specs(["python", "check.py"], {}) == []


def test_explicit_other_report_is_preserved_and_counts_stay_unknown():
    config = {"structured_reports": [{"format": "custom-json", "path": "report.json", "required": True}]}
    specs = report_specs(["custom"], config)
    assert specs == config["structured_reports"] and specs is not config["structured_reports"]
    summary = check_summary(output(), {}, {}, [{**specs[0], "reference": "report-ref"}])
    assert summary["structured_reports"][0]["reference"] == "report-ref"
    assert summary["test_counts"]["passed"] is None


def test_aggregate_distinguishes_requested_missing_and_failed():
    summaries = [check_summary(output(), {}, {}),
                 check_summary(output(check_id="failed", outcome="failed", exit_code=1), {}, {}),
                 check_summary(output(check_id="missing", outcome="unavailable", exit_code=None), {}, {})]
    result = aggregate(["suite", "failed", "missing", "absent"], summaries, False)
    assert result["completed_check_ids"] == ["suite", "failed"]
    assert result["missing_check_ids"] == ["missing", "absent"]
    assert result["outcomes"]["failed"] == "failed"
    assert result["evidence_complete"] is False and result["source_unchanged"] is False

