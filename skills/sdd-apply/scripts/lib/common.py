"""Filesystem primitives and native Git fixture compatibility."""
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


def validate_symlink(root, path):
    try:
        target = resolve(path, strict=True)
    except (OSError, RuntimeError) as exc:
        raise Rejected("invalid_symlink", f"Cannot resolve symlink {path}: {exc}") from exc
    require(target.is_relative_to(root), "path_escape", f"Symlink leaves worktree: {path} -> {target}")
    require(".git" not in (part.lower() for part in target.relative_to(root).parts),
            "git_path", f"Symlink points into Git metadata: {path}")
    require(target.is_file() or target.is_dir(), "invalid_symlink", f"Expected file or directory: {path}")


def contained(root, relative):
    return next(contained_paths(root, [relative]))


def contained_paths(root, relatives):
    """Resolve a shared root once while checking every requested child."""
    root = resolve(root)
    root_parts = tuple(part.lower() for part in root.parts) if os.name == "nt" else root.parts
    for relative in relatives:
        path = resolve(root / relative)
        parts = tuple(part.lower() for part in path.parts) if os.name == "nt" else path.parts
        require(len(parts) > len(root_parts) and parts[:len(root_parts)] == root_parts,
                "path_escape", str(relative))
        require(".git" not in [p.lower() for p in parts[len(root_parts):]], "git_path", str(relative))
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
