"""Filesystem path identity; the default resolver follows real filesystem links."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


_resolver = ContextVar("sdd_apply_path_resolver", default=None)


def resolve(path, strict=False):
    resolver = _resolver.get()
    path = Path(path)
    return path.resolve(strict=strict) if resolver is None else resolver(path, strict=strict)


@contextmanager
def use_path_resolver(resolver):
    token = _resolver.set(resolver)
    try:
        yield
    finally:
        _resolver.reset(token)
