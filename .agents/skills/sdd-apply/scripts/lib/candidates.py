"""Content-addressed candidate artifacts; references never replace validation."""
import json
import re
from . import artifact_storage as artifacts
from .common import digest, require, write_json


def directory_for(state):
    from .state import execution_directory
    return execution_directory(state["basis"])


def resolve(state, value):
    """Read a verified artifact or retain compatibility with inline candidates."""
    require(isinstance(value, dict), "candidate_reference", "Candidate must be an object")
    if set(value) == {"source", "manifest", "checks", "root"}:
        return value
    sha256 = value.get("sha256")
    require(isinstance(sha256, str) and re.fullmatch(r"[0-9a-f]{64}", sha256)
            and set(value) == {"candidate_id", "sha256", "path", "root"}
            and value["candidate_id"] == "candidate-" + sha256
            and value["path"] == f"candidates/{sha256}.json",
            "candidate_reference", "Use the complete script-issued candidate reference")
    path = artifacts.contained(directory_for(state), value["path"])
    require(artifacts.is_file(path), "candidate_missing", "Candidate artifact is missing: " + value["path"])
    try:
        payload = json.loads(artifacts.read_text(path))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Candidate artifact is unreadable: " + value["path"]) from exc
    require(isinstance(payload, dict) and set(payload) == {"source", "manifest", "checks", "root"}
            and digest(payload) == sha256 and payload["root"] == value["root"],
            "candidate_corrupt", "Candidate artifact or reference changed: " + value["path"])
    return payload


def store(state, payload):
    sha256 = digest(payload)
    reference = {"candidate_id": "candidate-" + sha256, "sha256": sha256,
                 "path": f"candidates/{sha256}.json", "root": payload["root"]}
    path = artifacts.contained(directory_for(state), reference["path"])
    if artifacts.exists(path):
        resolve(state, reference)  # Never silently replace corrupted evidence.
    else:
        write_json(path, payload)
    return reference


def same(state, left, right):
    if left is None or right is None:
        return left is right
    return resolve(state, left) == resolve(state, right)


def reference(state, value):
    return store(state, resolve(state, value)) if value is not None else None
