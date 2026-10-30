"""Persist and validate summaries through the existing execution object store."""
import base64
from copy import deepcopy
from pathlib import Path

from . import artifact_storage as artifacts
from .common import contained, digest, require
from .inputs import spec_modules
from .path_resolution import resolve
from .state_objects import StateObjects, encoded

summary = spec_modules("check_summary")
execution_kind = spec_modules("check_kinds").execution_kind


def reference(value):
    raw = encoded(value)
    sha = digest(raw)
    return {"path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha, "bytes": len(raw),
            "kind": "object" if isinstance(value, dict) else "array" if isinstance(value, list) else "string"}


def command_cwd(state, record, check):
    task = state["tasks"].get(record["task_id"]) if record["task_id"] else None
    worktree = task.get("worktree") if task else None
    root = Path(worktree["path"] if worktree and record["stage"] in {"baseline", "self", "independent"}
                else state["basis"]["project_root"])
    run = check["setup"] or check["run"]
    relative = run.get("cwd", check.get("cwd", "."))
    return str(root if relative == "." else contained(root, relative))


def context(state, record, checks, objects, check_run_id, persist=True, expected_run_id=None):
    put = objects.put if persist else reference
    roles = state.get("roles")
    require(isinstance(roles, dict), "unknown_role", "Evidence role registry is unavailable")
    role_id = record.get("role_id")
    require(isinstance(role_id, str) and bool(role_id), "unknown_role", "Evidence role identity is invalid")
    role = roles.get(role_id)
    require(isinstance(role, dict) and bool(role), "unknown_role", "Evidence role is missing or invalid")
    task = state["tasks"].get(record["task_id"]) if record["task_id"] else None
    return {"work_kind": state["basis"].get("work_kind", "change"),
            "work_id": state["change_id"], "run_id": state["run_id"] if expected_run_id is None else expected_run_id,
            "task_id": record["task_id"], "assignment_id": record["role_id"],
            "check_run_id": check_run_id, "role_id": record["role_id"], "stage": record["stage"],
            "role_trace": {key: deepcopy(role.get(key)) for key in
                           ("context_id", "host", "launch_ref", "agent_selection", "model_observation")},
            "basis_before": put(record.get("before", record.get("basis"))),
            "basis_after": put(record["after"]),
            "registry_revision": (task.get("check_registry", {}).get("revision", 0) if task else
                                  record["basis"].get("registry_revision", 0)),
            "registry": put(checks)}


def capture_reports(output, read_reports=True):
    """Snapshot declared bytes or failure before another command can overwrite them."""
    reports, limitations = [], []
    try:
        specs = summary.report_specs(output.get("command"), output.get("configuration", {}))
    except ValueError as exc:
        return {"reports": [], "limitations": [{"reason": str(exc)}]}
    for spec in specs:
        report = {**spec, "resolved_path": None}
        try:
            if not read_reports:
                raise ValueError("Report was not captured after command")
            declared = Path(spec["path"])
            path = resolve(declared if declared.is_absolute() else Path(output["cwd"]) / declared)
            report["resolved_path"] = str(path)
            report["raw"] = artifacts.read_bytes(path)
        except (OSError, ValueError) as exc:
            report["error"] = str(exc)
        reports.append(report)
    return {"reports": reports, "limitations": limitations}


def persist_reports(captured, objects, identity):
    reports = []
    for captured_report in captured["reports"]:
        report = {key: value for key, value in captured_report.items() if key != "raw"}
        report["reference"] = None
        if "raw" in captured_report:
            raw = captured_report["raw"]
            report["reference"] = objects.put({"identity": identity, "stream": "structured_report",
                "format": report["format"], "path": report["path"], "resolved_path": report["resolved_path"],
                "encoding": "base64", "content": base64.b64encode(raw).decode("ascii")})
            if report["format"] == "pytest-junit":
                try:
                    report["test_counts"] = summary.junit_counts(raw)
                except ValueError as exc:
                    report["error"] = str(exc)
        reports.append(report)
    return reports, captured["limitations"]


def persist(state, record, checks, directory, check_run_id):
    """Store raw streams separately; the run log and API carry references only."""
    objects = StateObjects(directory)
    identity = context(state, record, checks, objects, check_run_id)
    summaries, references = [], []
    by_id = {check["id"]: check for check in checks}
    for output in record["outputs"]:
        check = by_id[output["check_id"]]
        run = check["setup"] or check["run"]
        if "command" in run:
            output.setdefault("command", run["command"])
        output.setdefault("cwd", command_cwd(state, record, check))
        output.setdefault("procedure", run.get("procedure"))
        output.setdefault("configuration", run.get("configuration", check.get("configuration", {})))
        check_identity = {**identity, "check_id": output["check_id"],
                          "configuration": objects.put(output["configuration"])}
        raw_refs = {}
        for stream in ("stdout", "stderr"):
            if "command" in output and execution_kind(check) == "deterministic":
                binary = output.get(stream + "_base64")
                raw_refs[stream] = objects.put({"identity": check_identity, "stream": stream,
                    "encoding": "base64" if binary is not None else "text",
                    "content": binary if binary is not None else output.get(stream, "")})
        if output.get("procedure_log"):
            raw_refs["procedure"] = objects.put({"identity": check_identity, "stream": "procedure",
                "log": output["procedure_log"], "sha256": output["procedure_log_hash"]})
        captured = output.pop("_report_capture", None)
        if captured is None:
            captured = (capture_reports(output, read_reports=False) if execution_kind(check) == "deterministic"
                        else {"reports": [], "limitations": []})
        reports, limitations = persist_reports(captured, objects, check_identity)
        machine = summary.check_summary(output, check_identity, raw_refs, reports, limitations)
        summaries.append(machine)
        summary_reference = objects.put(machine)
        references.append(summary_reference)
        output["summary"] = summary_reference
        output["evidence_complete"] = machine["evidence_complete"]
        output.pop("stdout", None)
        output.pop("stderr", None)
        output.pop("stdout_base64", None)
        output.pop("stderr_base64", None)
    before = record.get("before", record.get("basis", {}).get("source"))
    aggregate = summary.aggregate([check["id"] for check in checks], summaries, before == record["after"])
    aggregate.update(schema_version=1, identity=identity, checks=references, diagnosis=None)
    record["summary"] = objects.put(aggregate)
    record["check_run_id"] = check_run_id
    return {**objects.pack(aggregate, root=True), "reference": record["summary"]}


def validate(state, record, checks, directory, expected_run_id=None, require_complete=True):
    """Every accepted summary must still resolve to this exact run and raw input."""
    objects = StateObjects(directory)
    require(record.get("summary") and record.get("check_run_id"), "evidence_missing",
            "Machine summary and check run identity are required")
    aggregate = objects.get(record["summary"])
    expected = context(state, record, checks, objects, record["check_run_id"],
                       persist=False, expected_run_id=expected_run_id)
    require(aggregate.get("identity") == expected, "evidence_basis", "Summary belongs to another basis or role")
    for field in ("basis_before", "basis_after", "registry"):
        objects.get(aggregate["identity"][field])
    require((not require_complete or aggregate.get("evidence_complete") is True) and aggregate.get("source_unchanged") is True,
            "evidence_incomplete", "Required raw or structured evidence is unavailable")
    require(aggregate.get("requested_check_ids") == [check["id"] for check in checks]
            and aggregate.get("missing_check_ids") == [], "evidence_basis", "Summary registry differs")
    require(aggregate.get("checks") == [output.get("summary") for output in record["outputs"]],
            "evidence_basis", "Summary check references differ from run")
    require([output["check_id"] for output in record["outputs"]] == [check["id"] for check in checks],
            "evidence_basis", "Every registered check must appear exactly once")
    by_id = {check["id"]: check for check in checks}
    for output in record["outputs"]:
        check = by_id[output["check_id"]]
        run = check["setup"] or check["run"]
        require(output.get("command") == run.get("command")
                and output.get("configuration") == run.get("configuration", check.get("configuration", {}))
                and output.get("cwd") == command_cwd(state, record, check),
                "evidence_command", "Summary must preserve the exact registered command, cwd and configuration")
        machine = objects.get(output["summary"])
        check_identity = {**expected, "check_id": output["check_id"],
                          "configuration": reference(output.get("configuration", {}))}
        require(all(machine.get(key) == value for key, value in check_identity.items()),
                "evidence_basis", "Check summary belongs to another basis")
        objects.get(machine["configuration"])
        require((not require_complete or machine.get("evidence_complete") is True)
                and machine.get("outcome") == output["outcome"]
                and machine.get("exit_code") == output.get("exit_code")
                and machine.get("command") == output.get("command"),
                "evidence_incomplete", "Summary does not preserve command evidence")
        raw_refs = machine.get("artifacts", {})
        require("command" not in output or execution_kind(check) != "deterministic" or {"stdout", "stderr"} <= raw_refs.keys(),
                "evidence_missing", "Command raw streams are required")
        require(not require_complete or execution_kind(check) == "deterministic" or "procedure" in raw_refs,
                "evidence_missing", "Semantic checks require their verifier's primary attestation")
        for stream, raw_reference in raw_refs.items():
            raw = objects.get(raw_reference)
            require(raw.get("identity") == check_identity and raw.get("stream") == stream,
                    "evidence_basis", "Raw evidence belongs to another run")
        reports = machine.get("structured_reports", [])
        declared = (summary.report_specs(output.get("command"), output.get("configuration", {}))
                    if execution_kind(check) == "deterministic" else [])
        require([{key: report.get(key) for key in ("format", "path", "required")} for report in reports] == declared,
                "evidence_basis", "Structured reports must match their exact registered declarations")
        for report in reports:
            require(not require_complete or not report["required"] or report.get("reference") and not report.get("error"),
                    "evidence_incomplete", "Required structured report is unavailable")
            if report.get("reference"):
                raw = objects.get(report["reference"])
                require(raw.get("identity") == check_identity and raw.get("stream") == "structured_report"
                        and raw.get("path") == report["path"] and raw.get("format") == report["format"]
                        and raw.get("resolved_path") == report["resolved_path"],
                        "evidence_basis", "Structured report belongs to another run")
    return aggregate

