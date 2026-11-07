"""Collect an immutable input snapshot without changing the consuming repository."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path

from inputs import class_source_file, source_description


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


def external_output(path, repository=None):
    path = Path(path).resolve()
    package = Path(__file__).resolve().parents[1]
    if inside(path, package) or (repository and inside(path, Path(repository).resolve())):
        raise ValueError("Write reports outside the skill and consuming repository")
    if any(part in {".agents", ".claude", ".codex", "skills"} for part in path.parts):
        raise ValueError("Write reports outside skill collections")
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
            sources[relative] = {**source_description(data.decode("utf-8-sig"), path.suffix),
                                 "sha256": digest(data), "language": path.suffix}
    return dict(sorted(sources.items()))


def identity(config, root):
    sources = inventory(config, root)
    measured_inputs = {path: row["sha256"] for path, row in sources.items()}
    for value in config.get("measurement_inputs", []):
        path = (root / value).resolve()
        if not inside(path, root):
            raise ValueError(f"Measurement input leaves repository: {value}")
        measured_inputs[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    source_state = digest(json.dumps(measured_inputs, sort_keys=True).encode())
    revision, dirty = None, None
    if shutil.which("git"):
        try:
            revision = run(["git", "rev-parse", "HEAD"], root).decode().strip()
            dirty = bool(run(["git", "status", "--porcelain", "--untracked-files=normal"], root))
        except ValueError:
            pass  # A source export is valid; it has no verified Git revision.
    return {"revision": revision, "dirty": dirty, "source_state": source_state,
            "source_files": sources, "measurement_inputs": measured_inputs}


def map_classes(config, root, sources):
    lookup, mappings, unresolved = defaultdict(list), {}, []
    for path, source in sources.items():
        lookup[source["package"], Path(path).name].append(path)
    for directory in config.get("class_directories", []):
        directory = (root / directory).resolve()
        if not directory.is_dir():
            raise ValueError(f"Missing compiled class directory: {directory}")
        for path in sorted(directory.rglob("*.class")):
            name, source_file = class_source_file(path.read_bytes())
            candidates = lookup[name.rpartition(".")[0], source_file]
            if len(candidates) == 1:
                if name in mappings and mappings[name] != candidates[0]:
                    raise ValueError(f"Conflicting JVM class {name}")
                mappings[name] = candidates[0]
            else:
                unresolved.append({"class": name, "source_file": source_file, "candidates": candidates})
    for name, path in config.get("class_files", {}).items():
        if path not in sources:
            raise ValueError(f"Explicit mapping is outside source inventory: {name} -> {path}")
        mappings[name] = path
    return dict(sorted(mappings.items())), unresolved


def collect(config, output):
    root = Path(config["repository"]).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository not found: {root}")
    output = external_output(output, root)
    if output.exists():
        raise ValueError("Snapshot output already exists; choose a new directory")
    output.mkdir(parents=True)
    before = identity(config, root)
    mappings, mapping_gaps = map_classes(config, root, before["source_files"])
    mapping_states = []
    if config.get("class_directories"):
        mapping_states.append(config.get("bytecode_source_state"))
    if config.get("class_files"):
        mapping_states.append(config.get("class_files_source_state"))
    mapping_status = ("unusable" if any(state and state != before["source_state"] for state in mapping_states)
                      else "usable" if mapping_states and all(mapping_states) else "limited")
    artifacts, gaps = {}, []
    supported = {"dependencies", "history", "sizes", "complexity", "coverage"}
    for name, spec in sorted(config.get("artifacts", {}).items()):
        if name not in supported:
            raise ValueError(f"Unknown artifact: {name}")
        metadata = dict(spec)
        try:
            if spec.get("collect"):
                if name == "history":
                    if before["revision"] is None:
                        raise ValueError("Git history needs a repository with HEAD")
                    argv = ["git", "-c", "core.quotePath=false", "log", "--no-merges", "--no-renames",
                            "--date=short", "--format=--%H--%ad--%an", "--numstat", before["revision"]]
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
                metadata["revision"] = before["revision"]
                metadata["source_state"] = (config.get("bytecode_source_state") if name == "dependencies"
                                             else before["source_state"])
            else:
                path = Path(spec["path"])
                if not path.is_absolute():
                    raise ValueError(f"Artifact path must be absolute: {name}")
                data = path.read_bytes()
                metadata["imported_from"] = str(path)
            raw_path = output / f"{name}.raw"
            raw_path.write_bytes(data)
            metadata.update(path=raw_path.name, sha256=digest(data), collected_at=datetime.now(timezone.utc).isoformat())
            metadata.setdefault("source_root", str(root))
            artifacts[name] = metadata
        except (OSError, ValueError) as error:
            gaps.append({"artifact": name, "reason": str(error)})
    after = identity(config, root)
    if before != after:
        raise ValueError("Source state changed during collection; discard this incomplete snapshot and collect again")
    snapshot = {"schema_version": 1, "repository": str(root), **before,
                "scope": config.get("scope", {}), "modules": config.get("modules", {}),
                "package_prefixes": config.get("package_prefixes", []),
                "exclude_classes": config.get("exclude_classes", []),
                "class_files": mappings, "mapping_gaps": mapping_gaps,
                "mapping_status": mapping_status, "mapping_source_states": mapping_states,
                "artifacts": artifacts, "gaps": gaps,
                "configuration": config}
    (output / "snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return snapshot
