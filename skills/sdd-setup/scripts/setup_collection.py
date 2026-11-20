"""Verify a project's collection task before registering it in SDD settings."""

import json
from pathlib import Path
import re
import sys

from setup_core import PACKAGE, read_bytes, read_json, replace_file, require, safe_target, setup_lock


def check_tools(tools, project, execute):
    require(isinstance(tools, dict) and tools, "List each required mise tool and its executable names")
    records = json.loads(execute(["mise", "ls", "--current", "--json"]))
    for tool, binaries in tools.items():
        require(isinstance(binaries, list) and binaries, f"List the executables provided by {tool}")
        installs = []
        for record in records.get(tool, []):
            source = (record.get("source") or {}).get("path")
            if source and record.get("active") and record.get("installed") and record.get("install_path") and (
                project / source
            ).resolve().is_relative_to(project):
                installs.append(Path(record["install_path"]).resolve())
        require(installs, f"Configure and install {tool} in project mise settings")
        for binary in binaries:
            require(isinstance(binary, str) and re.fullmatch(r"[\w.+][\w.+-]*", binary),
                    f"Expected executable name for {tool}")
            resolved = Path(execute(["mise", "which", binary]).decode().strip())
            require(resolved.is_absolute() and resolved.is_file() and
                    any(resolved.resolve().is_relative_to(base) for base in installs),
                    f"{binary} must resolve to the project-configured mise installation of {tool}")


def configure_collection(project, request):
    project = project.resolve(strict=True)
    # Only this setup route depends on the companion architect's report readers.
    scripts = PACKAGE.parent / "sdd-architect" / "scripts"
    require((scripts / "collection.py").is_file(), "Install sdd-architect alongside sdd-setup")
    sys.path.insert(0, str(scripts))
    from analysis_policy import load_policy
    from audit_configuration import resolve_project_path, validate_audit_configuration, validate_collection_settings
    from collection import inventory, map_classes, run
    from inputs import detekt
    from project_status import prepare_status

    settings = validate_collection_settings(request["collection"], project)
    command = settings["command"]
    require(len(command) >= 3 and command[:2] == ["mise", "run"] and not command[2].startswith("-"),
            "Select one project task as [\"mise\", \"run\", \"<task>\"]")
    scope = validate_audit_configuration(request["scope"])
    require(not scope.get("artifacts"), "Declare reports in collection.artifacts")
    require(scope.get("source_roots") and scope.get("modules") and scope.get("package_prefixes")
            and (scope.get("class_files") or scope.get("class_directories")), "Provide the production audit scope")
    for field in ("source_roots", "test_roots", "class_directories"):
        for path in scope.get(field, []):
            resolve_project_path(path, project, field)
    policy = load_policy(project)
    def execute(argv):
        return run(argv, project, policy)

    path = safe_target(project, ".sdd/settings.json")
    before = read_bytes(path)
    current = read_json(path) if before is not None else {"schema_version": 1}
    require(isinstance(current, dict) and type(current.get("schema_version")) is int
            and current["schema_version"] == 1, "Expected settings schema_version 1")
    architect = current.setdefault("architect", {})
    require(isinstance(architect, dict), "settings.architect must be an object")
    check_tools(request["tools"], project, execute)
    execute(command)
    artifacts = settings["artifacts"]
    raw = {name: resolve_project_path(spec["path"], project, name).read_text(encoding="utf-8-sig")
           for name, spec in artifacts.items()}
    sources = inventory(scope, project)
    mappings, gaps = map_classes(scope, project, sources)
    require(not gaps, f"Incomplete JVM source mapping: {gaps[:3]}")
    detekt(raw["complexity"], project / artifacts["complexity"].get("source_root", "."))
    prepare_status(scope, sources, mappings, raw, artifacts, policy, repository=project)
    with setup_lock(project, "collection"):
        require(read_bytes(path) == before, "Project settings changed during verification; repeat setup")
        changed = architect.get("collection") != settings
        if changed:
            architect["collection"] = settings
            replace_file(path, (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"changed": changed, "command": command, "reports": sorted(artifacts)}
