"""Locate the versioned SDD dependency before importing its public modules."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

def locate(explicit=None, legacy=None, work_kind="change"):
    if explicit is not None and legacy is not None:
        raise ValueError("Choose sdd_shared or legacy sdd_spec, not both")
    root = (Path(explicit) if explicit is not None else
            Path(legacy).resolve().parent / "sdd-shared" if legacy is not None else
            Path(__file__).resolve().parents[2] / "sdd-shared")
    root = root.resolve()
    try:
        api = json.loads((root / "api.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Install matching sdd-shared alongside the consumer or supply sdd_shared: {root}") from exc
    if type(api) is not dict or type(api.get("api_version")) is not int or api["api_version"] != 2:
        raise ValueError(f"Incompatible sdd-shared API; expected 2: {root}")
    if work_kind not in ("change", "refactoring"):
        raise ValueError(f"Unsupported SDD work kind: {work_kind}; correct the selection")
    schemas = api.get("document_schemas")
    if (not isinstance(schemas, dict) or not isinstance(schemas.get(work_kind), dict)
            or any(schemas[work_kind].get(kind) != [2] for kind in ("state", "review", "decisions"))):
        raise ValueError(f"sdd-shared does not support {work_kind} checkpoint formats v2; install the matching SDD bundle: {root}")
    if work_kind == "refactoring":
        kinds, schemas = api.get("work_kinds"), api.get("document_schemas")
        if (not isinstance(kinds, list) or "refactoring" not in kinds
                or not isinstance(schemas, dict) or not isinstance(schemas.get("refactoring"), dict)
                or any(schemas["refactoring"].get(kind) != [1] for kind in ("proposal", "design", "tasks"))):
            raise ValueError(f"sdd-shared does not support refactoring v1; install the matching SDD bundle: {root}")
    required = ["SKILL.md", "scripts/sdd_shared/__init__.py"]
    required += [f"scripts/{name}.py{suffix}" for name in ("check", "snapshot", "resolve_agent", "checkpoint") for suffix in ("", ".lock")]
    required += [f"scripts/sdd_shared/{name}.py" for name in ("documents", "paths", "validation", "snapshots", "reviews", "subagents", "checkpoints", "checkpoint_git")]
    if work_kind == "refactoring":
        required += ["scripts/sdd_shared/refactoring.py", "scripts/sdd_shared/refactoring_validation.py",
                     "references/document-format-refactoring.md", "schemas/refactoring.schema.json"]
    if any(not (root / item).is_file() for item in required):
        raise ValueError(f"Incomplete sdd-shared package: {root}")
    return root

def load(root, name, work_kind="change"):
    root = locate(explicit=root, work_kind=work_kind)
    key = "_sdd_shared_" + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if key not in sys.modules:
        package = root / "scripts/sdd_shared"
        spec = importlib.util.spec_from_file_location(key, package / "__init__.py", submodule_search_locations=[str(package)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key].module(name)
