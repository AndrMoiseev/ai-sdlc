"""Filesystem and Git primitives shared by deterministic operations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone


class Rejected(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise Rejected(code, message)


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path != root, "path_escape", str(relative))
    require(".git" not in [p.lower() for p in path.relative_to(root).parts], "git_path", str(relative))
    return path


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data if isinstance(data, bytes) else data.encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    atomic(path, json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def git(root, *args, env=None, check=True, raw=False):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=env)
    require(not check or result.returncode == 0, "git_failed", result.stderr.decode("utf-8", "replace"))
    return result.stdout if raw else result.stdout.decode("utf-8", "replace").strip()


def source_snapshot(root, exclude=(), include=()):
    root = Path(root).resolve()
    names = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", raw=True).decode("utf-8").split("\0")
    modes = {}
    for record in git(root, "ls-files", "--stage", "-z", raw=True).decode("utf-8").split("\0"):
        if record:
            meta, name = record.split("\t", 1)
            mode, _, stage = meta.split()
            require(stage == "0", "unmerged_index", name)
            modes[name] = mode
    files = {}
    for name in sorted(set(filter(None, names)) | set(include)):
        if any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclude):
            continue
        lexical = root / name
        require(not lexical.is_symlink(), "unsupported_file", name)
        path = contained(root, name)
        require(not path.is_dir(), "unsupported_file", f"Directory/submodule is not a supported source file: {name}")
        if path.is_file():
            executable = bool(path.stat().st_mode & 0o111)
            mode = modes.get(name, "100644") if os.name == "nt" else ("100755" if executable else "100644")
            require(mode in {"100644", "100755"}, "unsupported_file", f"Unsupported Git mode {mode}: {name}")
            files[name] = {"sha256": digest(path.read_bytes()), "executable": executable, "git_mode": mode}
        elif name in names:
            files[name] = None
    return {"files": files, "digest": digest(files)}
