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
def preparation(repositories):
    from unittest.mock import patch
    from check_commands import run_command
    from lib.repository import use_repositories
    from lib.state_storage import use_storage
    from lib.artifact_storage import use_artifacts
    from memory_state import MemoryStates
    states = MemoryStates()
    with use_repositories(repositories), use_storage(states), use_artifacts(states.artifacts), \
            patch("lib.verification.run_command", run_command):
        yield states


class Checkpoint:
    def __init__(self, workspace, driver, repositories, states):
        assert isinstance(repositories, MemoryRepositories)
        self.workspace = Path(workspace).resolve(strict=True)
        assert driver.directory.is_relative_to(self.workspace)
        self.driver = copy(driver)
        self.repositories = deepcopy(repositories.repos)
        self.artifact_directories = set(states.artifacts.directories)
        self.files, self.directories = {}, []
        for path in self.workspace.rglob("*"):
            assert not path.is_symlink()
            relative = path.relative_to(self.workspace)
            if path.is_dir():
                self.directories.append(relative)
            else:
                self.files[relative] = path.read_bytes(), path.stat().st_mode
        for path, data in states.artifacts.files.items():
            self.files[path.relative_to(self.workspace)] = data, 0o100644
        for path, store in states.stores.items():
            self.files[(path / "state.json").relative_to(self.workspace)] = store.read(), 0o100644

    def restore(self, repositories, states):
        from memory_state import MemoryStates
        assert isinstance(repositories, MemoryRepositories)
        assert isinstance(states, MemoryStates)
        states.stores.clear()
        states.artifacts.roots.clear()
        states.artifacts.files.clear()
        states.artifacts.directories = set(self.artifact_directories)
        states(self.driver.directory)
        source = {relative: data for relative, data in self.files.items()
                  if not (self.workspace / relative).is_relative_to(self.driver.directory)}
        restore(self.workspace, source, set(self.directories))
        self.driver.directory.mkdir(parents=True, exist_ok=True)
        for relative, (content, mode) in self.files.items():
            path = self.workspace / relative
            if path == self.driver.directory / "state.json":
                states(path.parent).replace(content)
            elif path.is_relative_to(self.driver.directory):
                states.artifacts.write(path, content)
        repositories.repos = deepcopy(self.repositories)
        for repo in repositories.repos.values():
            repo.factory = repositories
        return copy(self.driver)
