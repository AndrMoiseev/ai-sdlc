"""Repository operations used by execution; implementations are scoped per caller.

The factory receives an absolute worktree path. Commit/tree identifiers and
transfer bytes are opaque to callers. Mutations must preserve unrelated index
entries; failed patch application may leave conflicts for explicit resolution.
Recovery journals and acceptance decisions belong to the execution layer.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


_factory = ContextVar("sdd_apply_repositories", default=None)


def repository(root):
    from .git_repository import GitRepository
    return (_factory.get() or GitRepository)(Path(root).absolute())


@contextmanager
def use_repositories(factory):
    """Inject a repository implementation for this operation/context only."""
    token = _factory.set(factory)
    try:
        yield factory
    finally:
        _factory.reset(token)
