"""Collect current evidence and complete the measurement catalog in one operation."""

import json
import os
import re
import signal
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path

from analysis_policy import load_policy
from audit_configuration import resolve_project_path, validate_audit_configuration
from inputs import class_source_file, relative_path, source_description
from measurements import CATALOG, write_jsonl


def run(argv, cwd, policy):
    timeout = policy["runtime"]["command_timeout_seconds"]
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=False, **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False,
                           capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise ValueError(f"Command timed out after {timeout}s: {argv[0]}") from None
    if process.returncode:
        detail = stderr.decode('utf-8', errors='replace')[-policy["runtime"]["stderr_tail_characters"]:]
        raise ValueError(f"Command failed ({process.returncode}): {argv!r}\n{detail}")
    return stdout


def inside(path, root):
    return path == root or root in path.parents


def report_output(path, repository, directory=False):
    path = Path(path).resolve()
    package = Path(__file__).resolve().parents[1]
    if inside(path, package) or any(part in {".agents", ".claude", ".codex", "skills"} for part in path.parts):
        raise ValueError("Write reports outside skill collections")
    if not repository:
        raise ValueError("A project repository is required for report output")
    root = Path(repository).resolve()
    audits = root / "memory" / "tech-debt" / "audits"
    if not path.is_relative_to(audits) or len(path.relative_to(audits).parts) < (1 if directory else 2):
        raise ValueError("Write outputs inside <project-root>/memory/tech-debt/audits/<date-time>/")
    audit = path.relative_to(audits).parts[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}(?:\.\d{1,6})?Z", audit):
        raise ValueError("Audit directory needs a UTC date-time: YYYY-MM-DDTHH-mm-ss[.ffffff]Z")
    try:
        datetime.strptime(audit, "%Y-%m-%dT%H-%M-%S.%fZ" if "." in audit else "%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        raise ValueError(f"Invalid audit date-time: {audit}") from None
    return path


def inventory(config, root):
    sources = {}
    for source_root in config.get("source_roots", []):
        directory = (root / source_root).resolve()
        if not inside(directory, root) or not directory.is_dir():
            raise ValueError(f"Source root must be an existing directory inside repository: {source_root}")
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix not in {".kt", ".java"}:
                continue
            if not inside(path.resolve(), root):
                raise ValueError(f"Source symlink leaves repository: {path}")
            relative = path.relative_to(root).as_posix()
            if any(fnmatchcase(relative, pattern) for pattern in config.get("exclude_paths", [])):
                continue
            data = path.read_bytes()
            sources[relative] = {**source_description(data.decode("utf-8-sig"), path.suffix), "language": path.suffix}
    return dict(sorted(sources.items()))


def map_classes(config, root, sources):
    lookup, mappings, unresolved = defaultdict(list), {}, []
    for path, source in sources.items():
        lookup[source["package"], Path(path).name].append(path)
    for directory in config.get("class_directories", []):
        directory = (root / directory).resolve()
        if not directory.is_dir():
            unresolved.append({"reason": f"Missing compiled class directory: {directory}"})
            continue
        for path in sorted(directory.rglob("*.class")):
            try:
                name, source_file = class_source_file(path.read_bytes())
            except (OSError, ValueError, KeyError, TypeError) as error:
                unresolved.append({"reason": str(error), "class_file": str(path)})
                continue
            if any(fnmatchcase(name, pattern) for pattern in config.get("exclude_classes", [])):
                continue
            prefixes = config.get("package_prefixes", [])
            if prefixes and not any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes):
                continue
            candidates = lookup[name.rpartition(".")[0], source_file]
            if len(candidates) == 1:
                if name in mappings and mappings[name] != candidates[0]:
                    raise ValueError(f"Conflicting JVM class {name}")
                mappings[name] = candidates[0]
            else:
                unresolved.append({"class": name, "source_file": source_file, "candidates": candidates})
    for name, path in config.get("class_files", {}).items():
        path = relative_path(path, root)
        if path not in sources:
            raise ValueError(f"Explicit mapping is outside source inventory: {name} -> {path}")
        mappings[name] = path
    unresolved = [gap for gap in unresolved if gap.get("class") not in mappings]
    return dict(sorted(mappings.items())), unresolved


def collect(config, output, *, repository, full=True, java=None, detekt_jar=None):
    from analysis import prepare_measurements
    from candidate_groups import SELECTION_NAMES

    validate_audit_configuration(config)
    root = Path(repository).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository not found: {root}")
    for field in ("source_roots", "test_roots", "class_directories"):
        for path in config.get(field, []):
            resolve_project_path(path, root, field)
    for path in config.get("class_files", {}).values():
        resolve_project_path(path, root, "class_files")
    for name, spec in config.get("artifacts", {}).items():
        for field in ("path", "source_root"):
            if field in spec:
                resolve_project_path(spec[field], root, f"artifacts.{name}.{field}")
    policy = load_policy(root)
    output = report_output(output, root, directory=True)
    if any((output / name).exists() for name in ("collection.json", "metrics", "selections")):
        raise ValueError("Collection output already exists; choose a new report directory")
    output.mkdir(parents=True, exist_ok=True)
    description = {"status": "incomplete", "route": "full" if full else "focused", "analysis_policy": policy,
                   "parameters": {key: config.get(key, default) for key, default in (
                       ("source_roots", []), ("exclude_paths", []), ("package_prefixes", []),
                       ("exclude_classes", []), ("class_directories", []), ("modules", {}), ("scope", {}))},
                   "artifacts": {}, "gaps": [],
                   "selections": {name: {"path": f"selections/{name}.jsonl", "status": "incomplete", "records": None}
                                  for name in SELECTION_NAMES},
                   "outputs": {name: {"path": spec["path"], "status": "incomplete", "records": None,
                                      "reason": "Collection has not completed this calculation"}
                               for name, spec in CATALOG.items()}}

    def save_description():
        (output / "collection.json").write_text(json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    def block(reason):
        description["status"] = "blocked"
        description["gaps"].append({"reason": reason})
        save_description()
        raise ValueError(reason + "; stop the audit and resolve this prerequisite before continuing")

    save_description()
    source_error = None
    try:
        sources = inventory(config, root)
    except (OSError, ValueError) as error:
        sources, source_error = {}, str(error)
    try:
        mappings, mapping_gaps = map_classes(config, root, sources)
    except (OSError, ValueError) as error:
        mappings, mapping_gaps = {}, [{"reason": str(error)}]
    artifacts, raw = description["artifacts"], {}
    supported = {"dependencies", "history", "sizes", "complexity", "coverage", "kotlin"}
    unknown = set(config.get("artifacts", {})) - supported
    if unknown:
        raise ValueError(f"Unknown artifacts: {sorted(unknown)}")
    if full:
        missing = supported - config.get("artifacts", {}).keys()
        if missing:
            block("Missing configured sources: " + ", ".join(sorted(missing)))
        if source_error or mapping_gaps:
            block(source_error or "Incomplete JVM source mapping: " + str(mapping_gaps[:3]))
        if not config.get("source_roots") or not config.get("modules"):
            block("Configure production source roots and architectural module ownership")
        if not config.get("class_directories") and not config.get("class_files"):
            block("Compile production code and configure its JVM class directories")
    extensions = {"jdeps": ".txt", "class-csv": ".csv", "git-log": ".log", "scc": ".json",
                  "detekt-sarif": ".sarif", "jacoco": ".xml", "coverage-csv": ".csv", "kotlin-measurements": ".json", "git-history": ".json"}
    formats = {"dependencies": {"jdeps", "class-csv"}, "history": {"git-log", "git-history"}, "sizes": {"scc"},
               "complexity": {"detekt-sarif"}, "coverage": {"jacoco", "coverage-csv"}, "kotlin": {"kotlin-measurements"}}
    retained = {}
    for name in sorted(supported):
        spec = config.get("artifacts", {}).get(name)
        if spec is None:
            artifacts[name] = {"status": "unavailable", "reason": "No source configured"}
            continue
        metadata = {key: spec[key] for key in ("format", "tool", "version", "parser_version", "command", "source_root", "complete_mcc", "complete", "test_result", "limitations", "since", "until") if key in spec}
        try:
            if spec.get("collect"):
                if name == "kotlin":
                    from kotlin_measurements import collect_kotlin
                    data, details = collect_kotlin(sources, root, run, policy, java=java, detekt_jar=detekt_jar)
                    metadata.update(details)
                    argv = details["command"]
                elif name == "history" and full:
                    from history import collect_history
                    data, argv = collect_history(config, root, run, policy, sources)
                    metadata.update(format="git-history", tool="git", version=run(["git", "--version"], root, policy).decode().strip())
                elif name == "history":
                    argv = ["git", "-c", "core.quotePath=false", "log", "--no-merges", "--no-renames",
                            "--date=short", "--format=--%H--%ad--%an", "--numstat"]
                    for key in ("since", "until"):
                        if spec.get(key):
                            argv.append(f"--{key}={spec[key]}")
                    data = run(argv, root, policy)
                    metadata.update(format="git-log", tool="git", version=run(["git", "--version"], root, policy).decode().strip())
                elif name == "dependencies":
                    directories = config.get("class_directories", [])
                    if not directories:
                        raise ValueError("jdeps collection needs class_directories from the selected Gradle source sets")
                    argv = ["jdeps", "-verbose:class", "-filter:none", "--ignore-missing-deps", *directories]
                    data = run(argv, root, policy)
                    metadata.update(format="jdeps", tool="jdeps", version=run(["jdeps", "--version"], root, policy).decode().strip())
                elif name == "sizes":
                    roots = ["."] if full else config.get("source_roots", [])
                    if not roots:
                        raise ValueError("scc collection needs source_roots")
                    argv = ["scc", "--by-file", "--format", "json", "--no-cocomo", *roots]
                    data = run(argv, root, policy)
                    metadata.update(format="scc", tool="scc", version=run(["scc", "--version"], root, policy).decode().strip())
                else:
                    raise ValueError(f"{name}: run the project's selected Gradle task and import its report")
                metadata["command"] = argv
                path = None
            else:
                if spec.get("format") not in formats[name]:
                    raise ValueError(f"Unsupported {name} format: {spec.get('format')}")
                path = resolve_project_path(spec["path"], root, f"artifacts.{name}.path")
                data = path.read_bytes()
            raw_directory = (output / "raw").resolve()
            if not raw_directory.is_relative_to(output):
                raise ValueError("Raw report directory leaves the selected report")
            if path is not None and path.is_relative_to(raw_directory):
                raw_path = path
            elif path is not None and path in retained:
                raw_path = retained[path]
            else:
                raw_path = (raw_directory / (name + extensions[metadata["format"]])).resolve()
                if not raw_path.is_relative_to(output):
                    raise ValueError("Raw report path leaves the selected report")
                if raw_path.exists():
                    raise ValueError(f"Raw report output already exists: {raw_path}")
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(data)
            if path is not None:
                retained[path] = raw_path
            metadata.update(path=raw_path.relative_to(output).as_posix(), status="complete",
                            collected_at=datetime.now(timezone.utc).isoformat())
            metadata.setdefault("source_root", ".")
            raw[name] = data.decode("utf-8-sig")
        except (OSError, ValueError) as error:
            metadata.update(status="error", reason=str(error))
        artifacts[name] = metadata
        if full and metadata.get("status") != "complete":
            block(f"{name}: {metadata.get('reason', 'source unavailable')}")
    measurements, outcomes, selections, gaps = prepare_measurements(
        config, sources, mappings, mapping_gaps, raw, artifacts, policy, source_error, repository=root)
    description["gaps"] = gaps
    if full:
        failed = [name for name, metadata in artifacts.items() if metadata.get("status") != "complete"]
        if failed:
            block("Invalid measurement sources: " + ", ".join(failed))
        from project_status import prepare_status
        try:
            quality = prepare_status(config, sources, mappings, raw, artifacts, policy, repository=root)
        except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
            block(str(error))
        quality_path = output / "metrics" / "quality-indicators.json"
        quality_path.parent.mkdir(parents=True, exist_ok=True)
        quality_path.write_text(json.dumps(quality, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        description["quality_indicators"] = {"path": "metrics/quality-indicators.json", "status": "complete"}
    for name, rows in measurements.items():
        write_jsonl(output / CATALOG[name]["path"], rows)
        description["outputs"][name] = {"path": CATALOG[name]["path"], "records": len(rows), **outcomes[name]}
    description["selections"] = {}
    for name, rows in selections.items():
        path = f"selections/{name}.jsonl"
        write_jsonl(output / path, rows)
        description["selections"][name] = {"path": path, "records": len(rows), "status": "complete"}
    description["status"] = "complete"
    save_description()
    return description
