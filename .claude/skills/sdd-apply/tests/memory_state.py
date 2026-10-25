"""State byte storage for rule tests; no alternate validation or event engine."""
from contextlib import contextmanager
from pathlib import Path
from fnmatch import fnmatch
import os
import json
from lib.artifact_storage import FileArtifacts


class MemoryArtifacts:
    def __init__(self):
        self.roots, self.files = set(), {}
        self.directories = set()
        self.disk = FileArtifacts()

    def owns(self, path):
        return any(Path(path).absolute().is_relative_to(root) for root in self.roots)

    def contained(self, root, relative):
        if not self.owns(root):
            return self.disk.contained(root, relative)
        from lib.common import require
        root = Path(os.path.abspath(root))
        path = Path(os.path.abspath(root / relative))
        require(path.is_relative_to(root) and path != root, "path_escape", str(relative))
        require(".git" not in [p.lower() for p in path.relative_to(root).parts], "git_path", str(relative))
        return path

    def read(self, path):
        if not self.owns(path):
            return self.disk.read(path)
        try:
            return self.files[Path(path).absolute()]
        except KeyError:
            raise FileNotFoundError(str(path)) from None

    def write(self, path, data):
        if not self.owns(path):
            return self.disk.write(path, data)
        self.files[Path(path).absolute()] = bytes(data)

    def exists(self, path):
        if not self.owns(path):
            return self.disk.exists(path)
        path = Path(path).absolute()
        return (path in self.files or path in self.directories
                or path in self.roots and path.is_dir()
                or any(entry.is_relative_to(path) for entry in self.files))

    def is_file(self, path):
        return Path(path).absolute() in self.files if self.owns(path) else self.disk.is_file(path)

    def paths(self, directory, pattern):
        if not self.owns(directory):
            return self.disk.paths(directory, pattern)
        directory = Path(directory).absolute()
        children = {directory / path.relative_to(directory).parts[0] for path in self.files.keys() | self.directories
                    if path != directory and path.is_relative_to(directory)}
        return sorted(path for path in children if fnmatch(path.name, pattern))

    def remove(self, path):
        if not self.owns(path):
            return self.disk.remove(path)
        key = Path(path).absolute()
        if key not in self.files:
            raise FileNotFoundError(str(path))
        self.directories.update(parent for parent in key.parents if self.owns(parent))
        del self.files[key]


class MemoryStateStorage:
    def __init__(self):
        self.data = None
        self.locked = False

    def exists(self):
        return self.data is not None

    def read(self):
        if self.data is None:
            raise FileNotFoundError("state.json")
        return self.data

    def replace(self, data):
        self.data = bytes(data)

    def save(self, value):
        self.replace(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))

    @contextmanager
    def lock(self):
        if self.locked:
            raise ValueError("state_locked: another operation owns the state")
        self.locked = True
        try:
            yield
        finally:
            self.locked = False

    def recover_lock(self):
        raise AssertionError("Use native_state for process-owner recovery")


class MemoryStates:
    def __init__(self):
        self.stores = {}
        self.artifacts = MemoryArtifacts()

    def __call__(self, directory):
        key = Path(directory).absolute()
        self.artifacts.roots.add(key)
        if key not in self.stores:
            self.stores[key] = MemoryStateStorage()
        return self.stores[key]
