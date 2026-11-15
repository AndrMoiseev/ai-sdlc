#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read, check and atomically write the orchestrator's audit continuation state."""

import sys
sys.dont_write_bytecode = True

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def _validate_shape(value, rule, schema, location="state"):
    """Evaluate only the JSON Schema keywords used by audit-state.schema.json."""
    if "$ref" in rule:
        return _validate_shape(value, schema["$defs"][rule["$ref"].split("/")[-1]], schema, location)
    kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
    types = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}
    if not any(type(value) is types[kind] for kind in kinds):
        raise ValueError(f"{location}: expected {' or '.join(kinds)}")
    if "const" in rule and value != rule["const"]:
        raise ValueError(f"{location}: expected {rule['const']}")
    if "enum" in rule and value not in rule["enum"]:
        raise ValueError(f"{location}: expected one of {rule['enum']}")
    if isinstance(value, str) and "pattern" in rule and not re.search(rule["pattern"], value):
        raise ValueError(f"{location}: invalid or empty string")
    if isinstance(value, dict):
        missing = set(rule["required"]) - value.keys()
        unknown = value.keys() - rule["properties"].keys()
        if missing or unknown:
            raise ValueError(f"{location}: missing keys {sorted(missing)}; unknown keys {sorted(unknown)}")
        for key, item in value.items():
            _validate_shape(item, rule["properties"][key], schema, f"{location}.{key}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_shape(item, rule["items"], schema, f"{location}[{index}]")


def validate_audit_state(value):
    schema = read_json(ASSETS / "audit-state.schema.json")
    _validate_shape(value, schema, schema)
    assignments = {row["id"]: row for row in value["assignments"]}
    if len(assignments) != len(value["assignments"]):
        raise ValueError("Duplicate assignment ID")
    for identity, row in assignments.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", identity):
            raise ValueError("Assignment ID must be a single safe path component")
        assessment = row["assessment"]
        successor = assessment["next_assignment"]
        if assessment["status"] != "pending" and not assessment["reason"]:
            raise ValueError(f"{identity}: an assessment needs its reason")
        if successor is not None and (assessment["status"] != "follow_up" or successor not in assignments):
            raise ValueError(f"{identity}: next_assignment must name a recorded follow-up")
        seen = {identity}
        while successor is not None:
            if successor in seen:
                raise ValueError(f"{identity}: cyclic assignment follow-up")
            seen.add(successor)
            if successor not in assignments:
                raise ValueError(f"{identity}: unknown next_assignment {successor}")
            successor = assignments[successor]["assessment"]["next_assignment"]
        observation = row["host_observation"]
        if observation["state"] != "unknown" and not all(
            observation[key] for key in ("worker_id", "observed_at", "source")
        ):
            raise ValueError(f"{identity}: known host state needs worker, time and source")
        if bool(observation["observed_at"]) != bool(observation["source"]):
            raise ValueError(f"{identity}: host observation time and source belong together")
        if observation["observed_at"]:
            timestamp = observation["observed_at"]
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if not timestamp.endswith("Z") or "T" not in timestamp:
                    raise ValueError()
            except ValueError:
                raise ValueError(f"{identity}: observed_at must be a UTC ISO timestamp ending in Z") from None
    active = value["active_assignment"]
    next_assignment = value["next_step"]["assignment"] if value["next_step"] else None
    for identity in (active, next_assignment):
        if identity is not None and identity not in assignments:
            raise ValueError(f"Unknown assignment reference: {identity}")
    if active and assignments[active]["assessment"]["status"] != "pending":
        raise ValueError("The active assignment must have a pending assessment")
    if value["phase"] == "publication" and value["route"] != "full":
        raise ValueError("Only the full route has a publication phase")
    if value["phase"] == "complete":
        if active or value["next_step"] or value["remaining"] or value["blockers"] or value["plan"]["remaining"]:
            raise ValueError("Complete state cannot contain active or unfinished work")
        for identity, row in assignments.items():
            while row["assessment"]["next_assignment"] is not None:
                row = assignments[row["assessment"]["next_assignment"]]
            if row["assessment"]["status"] != "accepted":
                raise ValueError(f"{identity}: complete state needs an accepted result or completed follow-up")
    elif value["next_step"] is None:
        raise ValueError("Unfinished work needs a next_step")
    return value


def check_audit_state(value, read_record, exists):
    """Check material relationships through read-only adapters; return recoverable gaps.

    This cannot verify semantic acceptance, live host state, plan row meaning or permissions.
    The orchestrator supplies those observations and decisions.
    """
    validate_audit_state(value)
    issues = []

    def require(path, kind="file"):
        if not exists(path, kind):
            issues.append(f"Missing {kind}: {path}")

    def record(path, required=True):
        if not required and not exists(path, "file"):
            return None
        try:
            data = read_record(path)
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data
        except (OSError, ValueError) as error:
            issues.append(f"{path}: {error}")
            return None

    basis, plan = value["basis"], value["plan"]
    for path in basis["source_paths"]:
        require(path, "directory")
    for path in [basis["configuration"], basis["collection_plan"], *basis["artifacts"],
                 plan["path"], *plan["matched_tasks"], *plan["added_tasks"]]:
        if path is not None:
            require(path)
    active = value["active_assignment"]
    assignments = {row["id"]: row for row in value["assignments"]}
    publication_accepted = False
    for row in value["assignments"]:
        identity, assessment, observation = row["id"], row["assessment"], row["host_observation"]
        prefix = f"assignments/{identity}/"
        request = record(prefix + "request.json")
        launch = record(prefix + "launch.json", required=observation["worker_id"] is not None)
        result = record(prefix + "result.json", required=assessment["status"] != "pending")
        if launch is not None:
            worker = launch.get("worker_id")
            if not isinstance(worker, str) or not worker.strip():
                issues.append(f"{identity}: recover the launch worker_id from the host")
            elif worker != observation["worker_id"]:
                issues.append(f"{identity}: host observation worker_id does not match launch")
        if request is not None:
            assigned = request.get("assignment")
            if not isinstance(assigned, dict):
                issues.append(f"{identity}: request needs an assignment object")
                assigned = {}
            scope = assigned.get("scope")
            if not isinstance(scope, dict) or set(scope) != {"project", "work", "task"}:
                issues.append(f"{identity}: request needs project/work/task scope")
            if request.get("report") != value["report"] or assigned.get("id") != identity:
                issues.append(f"{identity}: request identity does not match state")
            if active == identity and request.get("phase") != value["phase"]:
                issues.append(f"{identity}: active request phase does not match state")
            if result is not None:
                if result.get("assignment_id") != identity or any(
                    key not in request or result.get(key) != request[key]
                    for key in ("report", "phase", "role")
                ) or result.get("scope") != scope:
                    issues.append(f"{identity}: result identity/scope does not match request")
        if result is not None and result.get("status") not in ("completed", "partial", "blocked"):
            issues.append(f"{identity}: unknown worker result status")
        if result is not None:
            artifacts = result.get("artifacts")
            if not isinstance(artifacts, list) or any(not isinstance(path, str) or not path.strip() for path in artifacts):
                issues.append(f"{identity}: result artifacts must be a list of primary file paths")
            else:
                for path in artifacts:
                    require(path)
                if assessment["status"] == "accepted" and not artifacts:
                    issues.append(f"{identity}: acceptance needs primary output paths")
        if result is not None and launch is None:
            issues.append(f"{identity}: result has no saved launch")
        if assessment["status"] == "accepted":
            if result is None or result.get("status") != "completed" or result.get("writing_stopped") is not True:
                issues.append(f"{identity}: acceptance needs a completed result with writing_stopped=true")
            if observation["state"] != "stopped":
                issues.append(f"{identity}: acceptance needs a recorded host stop observation")
            if request is not None and request.get("phase") == "publication":
                publication_accepted = True
        if (active and active != identity or assessment["next_assignment"] is not None) and launch is not None:
            if observation["state"] != "stopped":
                issues.append(f"{identity}: confirm the previous writer stopped before a successor")
        if (active or value["phase"] == "publication") and active != identity:
            last = row
            while last["assessment"]["next_assignment"] is not None and last["id"] != active:
                last = assignments[last["assessment"]["next_assignment"]]
            if last["assessment"]["status"] != "accepted" and last["id"] != active:
                issues.append(f"{identity}: assess the previous assignment or link its follow-up before continuing")
    if value["phase"] in {"publication", "complete"}:
        require("report.md")
        if plan["path"] is None:
            issues.append("Report delivery needs the current plan path")
        if plan["remaining"]:
            issues.append("Finish plan updates before publication")
    if value["phase"] == "complete" and value["route"] == "full" and not publication_accepted:
        issues.append("Complete full audit needs the accepted publication assignment")
    return issues


def audit_directory(path):
    from collection import report_output
    path = Path(path).absolute()
    if [parent.name for parent in list(path.parents)[:3]] != ["audits", "tech-debt", "memory"]:
        raise ValueError("Use <project-root>/memory/tech-debt/audits/<date-time>/")
    return report_output(path, path.parents[3], directory=True)


def state_path(directory):
    target = directory / "state.json"
    if not target.resolve().is_relative_to(directory.resolve()):
        raise ValueError("state.json must stay inside its audit directory")
    return target


def write_audit_state(directory, value):
    validate_audit_state(value)
    directory = audit_directory(directory)
    target = state_path(directory)
    if value["phase"] == "complete":
        issues = inspect_audit_state(directory, value)
        if issues:
            raise ValueError("Cannot complete audit: " + "; ".join(issues))
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def inspect_audit_state(directory, value):
    def resolve(path):
        resolved = (directory / path).resolve()
        if path.startswith("assignments/") and not resolved.is_relative_to(directory):
            raise ValueError("Assignment records must stay inside the audit directory")
        return resolved

    def exists(path, kind):
        resolved = resolve(path)
        return resolved.is_dir() if kind == "directory" else resolved.is_file()

    return check_audit_state(value, lambda path: read_json(resolve(path)), exists)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("read", "check", "write"))
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="Candidate JSON for write; otherwise read UTF-8 JSON from stdin")
    args = parser.parse_args(argv)
    try:
        directory = audit_directory(args.report_dir)
        if args.command == "write":
            value = read_json(args.input) if args.input else parse_json(sys.stdin.read())
            target = write_audit_state(directory, value)
            print(json.dumps({"state": str(target)}))
        else:
            if args.input:
                raise ValueError("--input belongs to write")
            value = validate_audit_state(read_json(state_path(directory)))
            if args.command == "read":
                print(json.dumps(value, ensure_ascii=False, indent=2))
            else:
                issues = inspect_audit_state(directory, value)
                print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
                return 1 if issues else 0
        return 0
    except (OSError, ValueError) as error:
        print(f"Audit state error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8-sig")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
