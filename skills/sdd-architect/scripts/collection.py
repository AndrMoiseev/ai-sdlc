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

from inputs import class_source_file, relative_path, source_description
from measurements import CATALOG, write_jsonl


def run(argv, cwd, timeout=60):
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
        raise ValueError(f"Command failed ({process.returncode}): {argv!r}\n{stderr.decode('utf-8', errors='replace')[-3000:]}")
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
    return dict(sorted(mappings.items())), unresolved


def collect(config, output):
    from analysis import prepare_measurements
    from candidate_groups import SELECTION_NAMES, candidate_group_limit

    limit = candidate_group_limit(config)
    root = Path(config["repository"]).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository not found: {root}")
    output = report_output(output, root, directory=True)
    if any((output / name).exists() for name in ("collection.json", "metrics", "selections")):
        raise ValueError("Collection output already exists; choose a new report directory")
    output.mkdir(parents=True, exist_ok=True)
    description = {"repository": str(root), "status": "incomplete",
                   "parameters": {key: config.get(key, default) for key, default in (
                       ("source_roots", []), ("exclude_paths", []), ("package_prefixes", []),
                       ("exclude_classes", []), ("class_directories", []), ("modules", {}), ("scope", {}),
                       ("candidate_group_limit", limit))},
                   "artifacts": {}, "gaps": [],
                   "selections": {name: {"path": f"selections/{name}.jsonl", "status": "incomplete", "records": None}
                                  for name in SELECTION_NAMES},
                   "outputs": {name: {"path": spec["path"], "status": "incomplete", "records": None,
                                      "reason": "Collection has not completed this calculation"}
                               for name, spec in CATALOG.items()}}

    def save_description():
        (output / "collection.json").write_text(json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

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
    supported = {"dependencies", "history", "sizes", "complexity", "coverage"}
    unknown = set(config.get("artifacts", {})) - supported
    if unknown:
        raise ValueError(f"Unknown artifacts: {sorted(unknown)}")
    extensions = {"jdeps": ".txt", "class-csv": ".csv", "git-log": ".log", "scc": ".json",
                  "detekt-sarif": ".sarif", "jacoco": ".xml", "coverage-csv": ".csv"}
    formats = {"dependencies": {"jdeps", "class-csv"}, "history": {"git-log"}, "sizes": {"scc"},
               "complexity": {"detekt-sarif"}, "coverage": {"jacoco", "coverage-csv"}}
    retained = {}
    for name in sorted(supported):
        spec = config.get("artifacts", {}).get(name)
        if spec is None:
            artifacts[name] = {"status": "unavailable", "reason": "No source configured"}
            continue
        metadata = {key: spec[key] for key in ("format", "tool", "version", "command", "source_root", "complete_mcc", "limitations", "since", "until") if key in spec}
        try:
            if spec.get("collect"):
                if name == "history":
                    argv = ["git", "-c", "core.quotePath=false", "log", "--no-merges", "--no-renames",
                            "--date=short", "--format=--%H--%ad--%an", "--numstat"]
                    for key in ("since", "until"):
                        if spec.get(key):
                            argv.append(f"--{key}={spec[key]}")
                    data = run(argv, root)
                    metadata.update(format="git-log", tool="git", version=run(["git", "--version"], root).decode().strip())
                elif name == "dependencies":
                    directories = [str((root / p).resolve()) for p in config.get("class_directories", [])]
                    if not directories:
                        raise ValueError("jdeps collection needs class_directories from the selected Gradle source sets")
                    argv = ["jdeps", "-verbose:class", "-filter:none", "--ignore-missing-deps", *directories]
                    data = run(argv, root)
                    metadata.update(format="jdeps", tool="jdeps", version=run(["jdeps", "--version"], root).decode().strip())
                elif name == "sizes":
                    roots = [str((root / p).resolve()) for p in config.get("source_roots", [])]
                    if not roots:
                        raise ValueError("scc collection needs source_roots")
                    argv = ["scc", "--by-file", "--format", "json", *roots]
                    data = run(argv, root)
                    metadata.update(format="scc", tool="scc", version=run(["scc", "--version"], root).decode().strip())
                else:
                    raise ValueError(f"{name}: run the project's selected Gradle task and import its report")
                metadata["command"] = argv
                path = None
            else:
                if spec.get("format") not in formats[name]:
                    raise ValueError(f"Unsupported {name} format: {spec.get('format')}")
                path = Path(spec["path"])
                if not path.is_absolute():
                    raise ValueError(f"Artifact path must be absolute: {name}")
                path = path.resolve()
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
            metadata.setdefault("source_root", str(root))
            raw[name] = data.decode("utf-8-sig")
        except (OSError, ValueError) as error:
            metadata.update(status="error", reason=str(error))
        artifacts[name] = metadata
    measurements, outcomes, selections, gaps = prepare_measurements(config, sources, mappings, mapping_gaps, raw, artifacts, source_error)
    description["gaps"] = gaps
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
