"""Validate audit inputs without persisting host paths or changing project settings."""

import json
import re
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import unquote


def project_path(value, field):
    """Check portable project-relative syntax independently of the host OS."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: expected a nonempty project-relative path")
    decoded = unquote(value)
    if (decoded != value or "\\" in value or PureWindowsPath(value).anchor
            or PurePosixPath(value).is_absolute() or ":" in value
            or value.startswith("~") or ".." in PurePosixPath(value).parts):
        raise ValueError(f"{field}: use a project-relative path with / and no parent traversal")
    return value


def resolve_project_path(value, root, field):
    path = (root / project_path(value, field)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{field}: path leaves the project through a symlink")
    return path


def validate_audit_configuration(value):
    if not isinstance(value, dict):
        raise ValueError("Audit configuration must be an object")
    fields = {"source_roots", "test_roots", "exclude_paths", "statistics_exclude_paths",
              "package_prefixes", "exclude_classes", "modules", "scope",
              "class_directories", "class_files", "artifacts"}
    unknown = value.keys() - fields
    if unknown:
        raise ValueError(f"Unknown audit configuration fields: {sorted(unknown)}; "
                         "pass the repository as a runtime argument")
    for field in ("source_roots", "test_roots", "exclude_paths",
                  "statistics_exclude_paths", "class_directories"):
        paths = value.get(field, [])
        if not isinstance(paths, list):
            raise ValueError(f"{field}: expected an array")
        for path in paths:
            project_path(path, field)
    mappings = value.get("class_files", {})
    if not isinstance(mappings, dict):
        raise ValueError("class_files: expected an object")
    for path in mappings.values():
        project_path(path, "class_files")
    artifacts = value.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts: expected an object")
    fields = {"path", "format", "tool", "version", "parser_version",
              "command", "source_root", "complete_mcc", "complete", "test_result",
              "limitations", "since", "until"}
    for name, spec in artifacts.items():
        if not isinstance(spec, dict) or spec.keys() - fields:
            raise ValueError(f"artifacts.{name}: unsupported artifact fields")
        for field in ("path", "source_root"):
            if field in spec:
                project_path(spec[field], f"artifacts.{name}.{field}")
        if "command" in spec and (not isinstance(spec["command"], list)
                                  or any(not isinstance(arg, str) for arg in spec["command"])):
            raise ValueError(f"artifacts.{name}.command: expected an argument array")

    def inspect(item, field):
        if isinstance(item, dict):
            for key, child in item.items():
                inspect(key, field)
                inspect(child, f"{field}.{key}")
        elif isinstance(item, list):
            for child in item:
                inspect(child, field)
        elif isinstance(item, str):
            # Commands and free-form provenance must not hide host paths in option values.
            for token in re.split(r"""[\s=;,"'()\[\]]+""", unquote(item)):
                token = token.lstrip("@")
                if (PureWindowsPath(token).anchor or token.lower().startswith(("/", "\\", "~", "file:"))
                        or ".." in PurePosixPath(token.replace("\\", "/")).parts):
                    raise ValueError(f"{field}: absolute paths and parent traversal are not audit configuration")
    inspect(value, "configuration")
    return value


FULL_FORMATS = {"dependencies": {"jdeps", "class-csv"}, "history": {"git-history"},
                "sizes": {"scc"}, "kotlin": {"kotlin-measurements"},
                "complexity": {"detekt-sarif"}, "coverage": {"jacoco"}}


def validate_collection_settings(value, root):
    """Validate the executable contract before any project process starts."""
    if not isinstance(value, dict) or set(value) != {"command", "artifacts"}:
        raise ValueError("architect.collection requires command and artifacts")
    command = value["command"]
    if not isinstance(command, list) or not command or not all(
        isinstance(arg, str) and arg.strip() and not any(ord(c) < 32 for c in arg) for arg in command
    ):
        raise ValueError("command must be a nonempty argument array")
    artifacts = value["artifacts"]
    validate_audit_configuration({"artifacts": artifacts})
    if artifacts.keys() != FULL_FORMATS.keys():
        raise ValueError(f"Missing configured sources: {sorted(FULL_FORMATS.keys() - artifacts.keys())}; "
                         f"unexpected sources: {sorted(artifacts.keys() - FULL_FORMATS.keys())}")
    for name, spec in artifacts.items():
        if spec.get("format") not in FULL_FORMATS[name]:
            raise ValueError(f"artifacts.{name}: expected {sorted(FULL_FORMATS[name])}")
        resolve_project_path(spec.get("path"), root, f"artifacts.{name}.path")
        resolve_project_path(spec.get("source_root", "."), root, f"artifacts.{name}.source_root")
    if artifacts["coverage"].get("complete") is not True or artifacts["coverage"].get("test_result") != "passed":
        raise ValueError("coverage must come from complete JaCoCo reporting after successful tests")
    return value


def project_collection(root):
    try:
        settings = json.loads(resolve_project_path(".sdd/settings.json", root, "settings").read_text(encoding="utf-8-sig"))
        if not isinstance(settings, dict) or type(settings.get("schema_version")) is not int or settings["schema_version"] != 1:
            raise ValueError("expected settings schema_version 1")
        return validate_collection_settings(settings["architect"]["collection"], root)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Configure architect.collection in .sdd/settings.json with sdd-setup: {error}") from error
