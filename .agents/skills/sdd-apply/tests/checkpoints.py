"""Reusable preparation produced by the real engine, restored before each case.

Only test-owned temporary workspaces and MemoryRepositories are supported. Each
restore replaces all files and copies the repository object graph, so mutations,
failed writes and fault injection cannot alter the saved checkpoint. Paths stay
fixed: candidate hashes and the event chain need no rewriting or resealing.
"""
from copy import copy, deepcopy
from contextlib import contextmanager
from pathlib import Path
import os

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
            patch("lib.verification.check_runner.run_command", run_command):
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
        # The factory is rebound on restore. Following it would also copy every
        # seed and unrelated template accumulated by the entire test session.
        self.repositories = deepcopy(repositories.repos, {id(repositories): None})
        self.artifact_directories = set(states.artifacts.directories)
        self.artifact_files = dict(states.artifacts.files)
        self.artifact_children = {path: set(children) for path, children in states.artifacts.children.items()}
        self.state_files = {path: store.read() for path, store in states.stores.items()}
        self.files, self.directories = {}, []
        self.memory_trees = {}
        for path in self.workspace.rglob("*"):
            assert not path.is_symlink()
            relative = path.relative_to(self.workspace)
            if path.is_dir():
                self.directories.append(relative)
            else:
                self.files[relative] = path.read_bytes(), path.stat().st_mode

    def restore(self, repositories, states, *, memory_worktree=False):
        """Use memory_worktree only for rules with explicitly arranged file edits.

        Source documents and executable check fixtures are still materialized;
        repository status/tree operations use the independent byte map instead.
        Tests of command side effects or source edits must retain the disk tree.
        """
        from memory_state import MemoryStates
        from lib.state_storage import FileStateStorage
        assert isinstance(repositories, MemoryRepositories)
        restore(self.workspace, self.files, set(self.directories))
        if isinstance(states, MemoryStates):
            states.stores.clear()
            states.artifacts.reset_roots()
            states.artifacts.files = dict(self.artifact_files)
            states.artifacts.children = {path: set(children) for path, children in self.artifact_children.items()}
            states.artifacts.directories = set(self.artifact_directories)
        else:
            assert states is FileStateStorage
            for directory in self.artifact_directories:
                directory.mkdir(parents=True, exist_ok=True)
            for path, content in self.artifact_files.items():
                path.write_bytes(content)
        for path, content in self.state_files.items():
            states(path).replace(content)
        self.driver.directory.mkdir(parents=True, exist_ok=True)
        repositories.repos = deepcopy(self.repositories)
        for repo in repositories.repos.values():
            repo.factory = repositories
            if memory_worktree and repo.root.is_relative_to(self.workspace):
                repo.working_files = dict(self.working_tree(repo))
        return copy(self.driver)

    def working_tree(self, repo):
        """Index immutable checkpoint bytes once; each restore copies the map."""
        if repo.root not in self.memory_trees:
            prefix = repo.root.relative_to(self.workspace)
            files = {}
            for path, (content, mode) in self.files.items():
                if not path.is_relative_to(prefix):
                    continue
                relative = path.relative_to(prefix)
                if ".git" in relative.parts:
                    continue
                name = relative.as_posix()
                default_mode = "100755" if os.name != "nt" and mode & 0o111 else "100644"
                files[name] = content, repo.index.get(name, (None, default_mode))[1]
            self.memory_trees[repo.root] = files
        return self.memory_trees[repo.root]
