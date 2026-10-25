"""Filesystem primitives and repository snapshot delegation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from .path_resolution import resolve


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
    return next(contained_paths(root, [relative]))


def contained_paths(root, relatives):
    """Resolve a shared root once while checking every requested child."""
    root = resolve(root)
    for relative in relatives:
        path = resolve(root / relative)
        require(path.is_relative_to(root) and path != root, "path_escape", str(relative))
        require(".git" not in [p.lower() for p in path.relative_to(root).parts], "git_path", str(relative))
        yield path


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
    from .artifact_storage import write
    write(path, json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def git(root, *args, env=None, check=True, raw=False):
    """Compatibility helper for native-Git fixtures; execution uses repository()."""
    from .git_repository import GitRepository
    result = GitRepository(root)._run(*args, env=env, check=check)
    return result.stdout if raw else result.stdout.decode("utf-8", "replace").strip()


def source_snapshot(root, exclude=(), include=()):
    from .repository import repository
    return repository(root).snapshot(exclude, include)
