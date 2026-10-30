"""Machine summaries from command metadata and explicit structured reports."""
from copy import deepcopy
from xml.etree import ElementTree

COUNT_FIELDS = ("collected", "passed", "failed", "skipped", "xfailed", "xpassed")
EXCERPT_LIMIT = 4096


def unknown_counts():
    return {**dict.fromkeys(COUNT_FIELDS), "unknown_fields": list(COUNT_FIELDS)}


def junit_counts(raw):
    """Pytest JUnit cannot identify all collected tests or non-strict XPASSes."""
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("JUnit declarations are unsupported")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid JUnit XML") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("Expected JUnit testsuite or testsuites")
    suites = list(root.iter("testsuite"))
    if not suites:
        raise ValueError("JUnit contains no testsuite")
    counts = unknown_counts()
    counts.update(passed=0, failed=0, skipped=0, xfailed=0)
    for suite in suites:
        cases = suite.findall("testcase")
        if suite.findall("testsuite"):
            continue
        for name in ("tests", "failures", "errors", "skipped"):
            value = suite.get(name)
            if value is not None and (not value.isdecimal()):
                raise ValueError("Invalid JUnit count: " + name)
        if suite.get("tests") is not None and int(suite.get("tests")) != len(cases):
            raise ValueError("JUnit test count does not match testcase records")
        observed = {"failures": sum(case.find("failure") is not None for case in cases),
                    "errors": sum(case.find("error") is not None for case in cases),
                    "skipped": sum(case.find("skipped") is not None for case in cases)}
        for field, value in observed.items():
            if suite.get(field) is not None and int(suite.get(field)) != value:
                raise ValueError("JUnit " + field + " count does not match testcase records")
        for case in cases:
            skipped = case.find("skipped")
            if case.find("failure") is not None or case.find("error") is not None:
                counts["failed"] += 1
            elif skipped is not None:
                if skipped.get("type") == "pytest.xfail":
                    counts["xfailed"] += 1
                else:
                    counts["skipped"] += 1
            else:
                counts["passed"] += 1
    counts["unknown_fields"] = [key for key in COUNT_FIELDS if counts[key] is None]
    return counts


def report_specs(command, configuration):
    """Read declared paths; never append flags or interpret shell command text."""
    configured = configuration.get("structured_reports", [])
    if not isinstance(configured, list):
        raise ValueError("structured_reports must be a list")
    reports = []
    for report in configured:
        if (not isinstance(report, dict) or set(report) != {"format", "path", "required"}
                or not isinstance(report["format"], str) or not report["format"]
                or not isinstance(report["path"], str) or not report["path"]
                or type(report["required"]) is not bool):
            raise ValueError("Structured report needs format, path and boolean required")
        reports.append(deepcopy(report))
    if len({(report["format"], report["path"]) for report in reports}) != len(reports):
        raise ValueError("Duplicate structured report")
    for index, arg in enumerate(command or []):
        if arg in {"--junitxml", "--junit-xml"}:
            if index + 1 == len(command) or not command[index + 1]:
                raise ValueError("Missing registered JUnit path")
            path = command[index + 1]
        elif arg.startswith(("--junitxml=", "--junit-xml=")):
            path = arg.split("=", 1)[1]
            if not path:
                raise ValueError("Missing registered JUnit path")
        else:
            continue
        if not any(r["path"] == path and r["format"] == "pytest-junit" for r in reports):
            reports.append({"format": "pytest-junit", "path": path, "required": True})
        else:
            for report in reports:
                if report["path"] == path and report["format"] == "pytest-junit":
                    report["required"] = True
    return reports


def excerpt(output, references):
    stream = "stderr" if output.get("stderr") else "stdout"
    value = output.get(stream, "")
    offset = max(0, len(value) - EXCERPT_LIMIT)
    return {"stream": stream, "reference": references.get(stream), "text": value[offset:],
            "offset": offset, "line": value.count("\n", 0, offset) + 1,
            "truncated": bool(offset)}


def check_summary(output, context, references, reports=(), limitations=()):
    counts = unknown_counts()
    errors = list(limitations)
    complete = output.get("outcome") not in {"unavailable", "planned_absence"}
    parsed = []
    for report in reports:
        error = report.get("error")
        if error:
            errors.append({"report": report["path"], "reason": error})
            if report["required"]:
                complete = False
        elif report["format"] == "pytest-junit":
            parsed.append(report["test_counts"])
    if parsed:
        for field in COUNT_FIELDS:
            values = [item[field] for item in parsed]
            counts[field] = sum(values) if all(value is not None for value in values) else None
        counts["unknown_fields"] = [field for field in COUNT_FIELDS if counts[field] is None]
    if limitations:
        complete = False
    machine = {**deepcopy(context), "schema_version": 1,
               "check_id": output["check_id"], "command": output.get("command"),
               "procedure": output.get("procedure"), "cwd": output.get("cwd"),
               "started_at": output.get("started_at"), "duration_seconds": output.get("duration_seconds"),
               "exit_code": output.get("exit_code"), "outcome": output["outcome"],
               "limitation": output.get("limitation", output.get("description")),
               "limitations": errors, "test_counts": counts, "evidence_complete": complete,
               "artifacts": deepcopy(references), "structured_reports": deepcopy(list(reports)),
               "excerpt": excerpt(output, references)}
    return machine


def aggregate(requested, summaries, source_unchanged):
    completed = [item["check_id"] for item in summaries
                 if item["outcome"] not in {"planned_absence", "unavailable"}]
    missing = [ident for ident in requested if ident not in completed]
    return {"requested_check_ids": list(requested), "completed_check_ids": completed,
            "missing_check_ids": missing,
            "outcomes": {item["check_id"]: item["outcome"] for item in summaries},
            "source_unchanged": source_unchanged,
            "evidence_complete": not missing and all(item["evidence_complete"] for item in summaries)}

