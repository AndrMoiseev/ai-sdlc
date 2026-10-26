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
        self.children = {}
        self._contained = {}
        self._ownership = {}
        self.disk = FileArtifacts()

    def register(self, root):
        name = os.path.normcase(str(root))
        if name not in self.roots:
            self.roots.add(name)
            self._ownership.clear()

    def reset_roots(self):
        self.roots.clear()
        self._ownership.clear()
        self._contained.clear()

    def owns(self, path):
        cacheable = isinstance(path, Path) and path.is_absolute() and ".." not in path.parts
        if cacheable and path in self._ownership:
            return self._ownership[path]
        if cacheable:
            name = os.path.normcase(str(path))
        else:
            name = os.path.normcase(os.path.abspath(path))
        owned = any(name == root or name.startswith(root.rstrip(os.sep) + os.sep)
                    for root in self.roots)
        if cacheable:
            self._ownership[path] = owned
        return owned

    def contained(self, root, relative):
        if not self.owns(root):
            return self.disk.contained(root, relative)
        root = Path(root).absolute()
        key = root, relative
        if key in self._contained:
            return self._contained[key]
        from lib.common import require
        root = Path(os.path.abspath(root))
        path = Path(os.path.abspath(root / relative))
        prefix = os.path.normcase(str(root)).rstrip(os.sep) + os.sep
        require(path != root and os.path.normcase(str(path)).startswith(prefix), "path_escape", str(relative))
        require(".git" not in [p.lower() for p in path.parts[len(root.parts):]], "git_path", str(relative))
        self._contained[key] = path
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
        path = Path(path).absolute()
        self.files[path] = bytes(data)
        self.children.setdefault(path.parent, set()).add(path)
        parent = path.parent
        while parent not in self.directories and self.owns(parent):
            self.directories.add(parent)
            if os.path.normcase(str(parent)) not in self.roots:
                self.children.setdefault(parent.parent, set()).add(parent)
            parent = parent.parent

    def exists(self, path):
        if not self.owns(path):
            return self.disk.exists(path)
        path = Path(path).absolute()
        return (path in self.files or path in self.directories
                or os.path.normcase(str(path)) in self.roots and path.is_dir())

    def is_file(self, path):
        return Path(path).absolute() in self.files if self.owns(path) else self.disk.is_file(path)

    def paths(self, directory, pattern):
        if not self.owns(directory):
            return self.disk.paths(directory, pattern)
        directory = Path(directory).absolute()
        return sorted(path for path in self.children.get(directory, ()) if fnmatch(path.name, pattern))

    def remove(self, path):
        if not self.owns(path):
            return self.disk.remove(path)
        key = Path(path).absolute()
        if key not in self.files:
            raise FileNotFoundError(str(path))
        del self.files[key]
        self.children[key.parent].discard(key)


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
        if directory in self.stores:
            return self.stores[directory]
        key = Path(directory).absolute()
        self.artifacts.register(key)
        if key not in self.stores:
            self.stores[key] = MemoryStateStorage()
        return self.stores[key]
