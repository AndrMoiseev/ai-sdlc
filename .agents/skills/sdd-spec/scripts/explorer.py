"""Disposable spec explorer artifacts; importable helper, not a CLI or journal."""

import hashlib
import json
from pathlib import Path
import re
import tempfile

from shared import load, locate


def create_directory(project_root, skill_roots, uv_cache):
    """Use the environment temp API, rejecting storage inside excluded roots."""
    base = Path(tempfile.gettempdir()).resolve()
    excluded = [Path(project_root).resolve(), *(Path(p).resolve() for p in skill_roots),
                Path(uv_cache).resolve()]
    if any(base == root or base.is_relative_to(root) for root in excluded):
        raise ValueError("System temporary directory is inside project, skills or uv cache")
    return Path(tempfile.mkdtemp(prefix="sdd-spec-explorer-", dir=base)).resolve()


def write_artifact(directory, name, value):
    """Save one explicitly named artifact, returning its absolute path and digest."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("Artifact name must be a plain filename")
    directory = Path(directory)
    if not directory.is_absolute():
        raise ValueError("Artifact directory must be absolute")
    path = directory.resolve() / name
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    # Exclusive creation preserves earlier evidence; a new attempt gets a new directory.
    with path.open("xb") as stream:
        stream.write(payload)
    return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}


def read_artifact(reference):
    """Read only digest-matching evidence; callers classify unavailable artifacts."""
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError("Missing artifact reference")
    path = Path(reference["path"])
    if not path.is_absolute():
        raise ValueError("Artifact reference must be absolute")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != reference.get("sha256"):
        raise ValueError("Artifact digest mismatch")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Artifact must contain an object")
    return value


def save_request(directory, assignment, selection, capabilities):
    """Persist the shared assignment after host evidence passes the capability gate."""
    contract = load(locate(), "explorer")
    contract.validate_assignment(assignment)
    gate = contract.check_capabilities(assignment, capabilities)
    if not gate["ready"]:
        raise ValueError(f"Explorer capabilities unavailable: {gate['unavailable']}")
    directory = Path(directory).resolve()
    for output in assignment["outputs"]:
        path = Path(output)
        if not path.is_absolute() or not path.resolve().is_relative_to(directory):
            raise ValueError("Explorer outputs must stay in its absolute temporary directory")
    if not isinstance(selection, dict) or not selection:
        raise ValueError("Preserve resolver selection evidence")
    request = {"assignment": assignment, "selection": selection, "capabilities": capabilities}
    return write_artifact(directory, assignment["id"] + ".request.json", request)


def validate_result(assignment, result):
    """Check result identity and required evidence, never judge approval or AC."""
    if not isinstance(result, dict):
        raise ValueError("Explorer result must be an object")
    for field in ("id", "kind", "scope", "basis"):
        if result.get(field) != assignment[field]:
            raise ValueError(f"Explorer result has foreign or stale {field}")
    if result.get("status") not in ("completed", "incomplete", "unavailable"):
        raise ValueError("Explorer result requires explicit status")
    launch = result.get("launch")
    if not isinstance(launch, dict) or not launch.get("context_id") or not launch.get("trace"):
        raise ValueError("Explorer result requires actual launch context and trace")
    if not isinstance(result.get("limitations"), list):
        raise ValueError("Explorer result requires limitations")
    if assignment["kind"] == "research":
        required = ("answer", "sources", "inspected_scope", "gaps", "assumptions", "questions")
    else:
        required = ("summary", "raw_artifacts", "diagnosis")
    if any(field not in result for field in required):
        raise ValueError("Explorer result is missing evidence fields")
    return result


def recover(request_reference, result_reference, current_basis, launch_reference=None):
    """Recover existing files only; no launch, rerun, state write or approval inference."""
    try:
        request = read_artifact(request_reference)
        assignment = load(locate(), "explorer").validate_assignment(request.get("assignment"))
        launch = read_artifact(launch_reference) if launch_reference is not None else None
        if assignment["basis"] != current_basis:
            raise ValueError("Assignment basis is stale")
        if result_reference is None:
            return {"status": "incomplete", "reason": "No received result",
                    "request": request, "launch": launch, "result": None}
        result = validate_result(assignment, read_artifact(result_reference))
        if launch is None or result["launch"] != launch:
            raise ValueError("Result launch differs from saved host launch evidence")
        return {"status": result["status"], "reason": None,
                "request": request, "launch": launch, "result": result}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"status": "unavailable", "reason": str(exc),
                "request": None, "launch": None, "result": None}
