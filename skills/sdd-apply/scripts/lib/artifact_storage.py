"""Execution artifacts as bytes; callers own paths, schemas and integrity checks."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


class FileArtifacts:
    def contained(self, root, relative):
        from .common import contained
        return contained(root, relative)

    def read(self, path):
        return Path(path).read_bytes()

    def write(self, path, data):
        from .common import atomic
        atomic(path, data)

    def exists(self, path):
        return Path(path).exists()

    def is_file(self, path):
        return Path(path).is_file()

    def paths(self, directory, pattern):
        return list(Path(directory).glob(pattern))

    def remove(self, path):
        Path(path).unlink()


_backend = ContextVar("sdd_apply_artifacts", default=FileArtifacts())


def contained(root, relative):
    return _backend.get().contained(root, relative)


def read_bytes(path):
    return _backend.get().read(path)


def read_text(path):
    return read_bytes(path).decode("utf-8")


def write(path, data):
    return _backend.get().write(path, data if isinstance(data, bytes) else data.encode("utf-8"))


def exists(path):
    return _backend.get().exists(path)


def is_file(path):
    return _backend.get().is_file(path)


def paths(directory, pattern="*"):
    return _backend.get().paths(directory, pattern)


def remove(path):
    return _backend.get().remove(path)


@contextmanager
def use_artifacts(backend):
    token = _backend.set(backend)
    try:
        yield backend
    finally:
        _backend.reset(token)
