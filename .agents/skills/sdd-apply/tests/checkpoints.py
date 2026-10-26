"""Reusable preparation produced by the real engine, restored before each case.

Only test-owned temporary workspaces and MemoryRepositories are supported. Each
restore replaces all files and copies the repository object graph, so mutations,
failed writes and fault injection cannot alter the saved checkpoint. Paths stay
fixed: candidate hashes and the event chain need no rewriting or resealing.
"""
from copy import copy, deepcopy
from contextlib import contextmanager
from pathlib import Path

from memory_repository import MemoryRepositories
from working_copy import restore


@contextmanager
def preparation(repositories, states=None):
    from unittest.mock import patch
    from check_commands import run_command
    from lib.repository import use_repositories
    from lib.state_storage import use_storage
    from lib.artifact_storage import use_artifacts
    from memory_state import MemoryStates
    states = states if states is not None else MemoryStates()
    with use_repositories(repositories), use_storage(states), use_artifacts(states.artifacts), \
            patch("lib.verification.run_command", run_command):
        yield states


class LazyCheckpoints:
    """Advance the real lifecycle only as far as requested, outside test mutations."""
    def __init__(self, workspace, repositories, steps):
        from memory_state import MemoryStates
        self.workspace, self.repositories = workspace, repositories
        self.states = MemoryStates()
        self.steps = iter(steps)
        self.saved = {}
        self.last = None

    def __getitem__(self, stage):
        if stage in self.saved:
            return self.saved[stage]
        with preparation(self.repositories, self.states):
            if self.last is not None:
                self.last.restore(self.repositories, self.states)
            while stage not in self.saved:
                try:
                    name, driver = next(self.steps)
                except StopIteration:
                    raise KeyError(stage) from None
                self.last = Checkpoint(self.workspace, driver, self.repositories, self.states)
                self.saved[name] = self.last
        return self.saved[stage]


class Checkpoint:
    def __init__(self, workspace, driver, repositories, states):
        assert isinstance(repositories, MemoryRepositories)
        self.workspace = Path(workspace).resolve(strict=True)
        assert driver.directory.is_relative_to(self.workspace)
        self.driver = copy(driver)
        self.repositories = deepcopy(repositories.repos)
        self.artifact_directories = set(states.artifacts.directories)
        self.artifact_files = dict(states.artifacts.files)
        self.artifact_children = {path: set(children) for path, children in states.artifacts.children.items()}
        self.state_files = {path: store.read() for path, store in states.stores.items()}
        self.files, self.directories = {}, []
        for path in self.workspace.rglob("*"):
            assert not path.is_symlink()
            relative = path.relative_to(self.workspace)
            if path.is_dir():
                self.directories.append(relative)
            else:
                self.files[relative] = path.read_bytes(), path.stat().st_mode

    def restore(self, repositories, states):
        from memory_state import MemoryStates
        assert isinstance(repositories, MemoryRepositories)
        assert isinstance(states, MemoryStates)
        states.stores.clear()
        states.artifacts.reset_roots()
        states.artifacts.files = dict(self.artifact_files)
        states.artifacts.children = {path: set(children) for path, children in self.artifact_children.items()}
        states.artifacts.directories = set(self.artifact_directories)
        for path, content in self.state_files.items():
            states(path).replace(content)
        restore(self.workspace, self.files, set(self.directories))
        self.driver.directory.mkdir(parents=True, exist_ok=True)
        repositories.repos = deepcopy(self.repositories)
        for repo in repositories.repos.values():
            repo.factory = repositories
        return copy(self.driver)
