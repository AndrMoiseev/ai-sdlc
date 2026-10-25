"""Stateful repository test implementation, with real working files for checks.

Models the execution interface, not Git command syntax. Transfer bytes are
opaque JSON; native patch syntax, hooks and filters are tested with real Git.
"""
from copy import deepcopy
from difflib import SequenceMatcher
from fnmatch import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil

from lib.common import contained, digest, require
from lib.artifact_storage import read_bytes as artifact_bytes


def identifier(value):
    return hashlib.sha1(repr(sorted(value.items())).encode()).hexdigest()


def merge_file(base, ours, theirs):
    """Model disjoint text edits; overlapping/binary edits report a conflict."""
    if not all(value is not None for value in (base, ours, theirs)):
        return None
    if any(b"\0" in value[0] for value in (base, ours, theirs)):
        return None
    mode = theirs[1] if ours[1] == base[1] else ours[1] if theirs[1] in (base[1], ours[1]) else None
    if mode is None:
        return None
    lines, edits = base[0].splitlines(keepends=True), []
    for content in (ours[0], theirs[0]):
        changed = content.splitlines(keepends=True)
        for tag, start, end, first, last in SequenceMatcher(None, lines, changed, autojunk=False).get_opcodes():
            edit = (start, end, changed[first:last])
            if tag == "equal" or edit in edits:
                continue
            if any(max(start, a) < min(end, b) or start == end == a == b or
                   a < start < b and start == end or start < a < end and a == b for a, b, _ in edits):
                return None
            edits.append(edit)
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = replacement
    return b"".join(lines), mode


def capture_seed(root, repo=None):
    from lib.git_repository import GitRepository
    repo = repo or GitRepository(root)
    files = repo.snapshot()["files"]
    return dict(head=repo.head(), branch=repo.branch(),
                files={name: (Path(root, name).read_bytes(), meta["git_mode"]) for name, meta in files.items() if meta})


class MemoryRepositories:
    def __init__(self, seeds):
        self.seeds = seeds
        self.repos = {}

    def __call__(self, root):
        root = Path(os.path.abspath(root))
        if root not in self.repos:
            seed = self.seeds.get(root)
            if seed is None:
                head = (root / ".git/HEAD").read_text().strip()
                if head.startswith("ref: "):
                    head = (root / ".git" / head[5:]).read_text().strip()
                seed = self.seeds[head]
            self.seed(root, seed)
        return self.repos[root]

    def seed(self, root, seed):
        root = Path(root).resolve()
        tree = identifier(seed["files"])
        store = dict(trees={tree: deepcopy(seed["files"])},
                     commits={seed["head"]: dict(tree=tree, parent=None, message="fixture")},
                     worktrees={root}, main_root=root, ignores=[])
        repo = MemoryRepository(self, root, store, seed["head"], seed["branch"])
        self.repos[root] = repo
        return repo


class MemoryRepository:
    def __init__(self, factory, root, store, head, branch=None):
        self.factory, self.root, self.store = factory, Path(root), store
        self._head, self._branch = head, branch
        self.index = deepcopy(store["trees"][store["commits"][head]["tree"]])
        self.conflicts = set()

    def head(self):
        return self._head

    def branch(self):
        return self._branch

    def has_conflicts(self):
        return bool(self.conflicts)

    def _ignore_patterns(self):
        patterns = list(self.store["ignores"])
        for path in (self.root / ".gitignore", self.store["main_root"] / ".git/info/exclude"):
            if path.is_file():
                patterns.extend(path.read_text().splitlines())
        return [pattern for pattern in patterns if pattern and not pattern.startswith("#")]

    def _files(self, exclude=(), include_ignored=False):
        result = {}
        patterns = self._ignore_patterns()
        for directory, dirs, files in os.walk(self.root):
            relative = Path(directory).relative_to(self.root)
            dirs[:] = [name for name in dirs if name != ".git" and
                       not any((relative / name).as_posix() == p.rstrip("/") for p in exclude)]
            for name in files:
                name = (relative / name).as_posix()
                if name == ".git" or any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclude):
                    continue
                if include_ignored or name in self.index or not any(fnmatch(name, pattern) for pattern in patterns):
                    path = self.root / name
                    require(not path.is_symlink(), "unsupported_file", name)
                    mode = self.index.get(name, (None, "100644"))[1] if os.name == "nt" else ("100755" if path.stat().st_mode & 0o111 else "100644")
                    result[name] = (path.read_bytes(), mode)
        return result

    def snapshot(self, exclude=(), include=()):
        require(not self.conflicts, "unmerged_index", "Unresolved test index")
        actual = self._files(exclude)
        for name in include:
            if name in actual:
                continue
            path = contained(self.root, name)
            if path.is_file():
                actual[name] = (path.read_bytes(), self.index.get(name, (None, "100644"))[1])
        names = set(actual) | {n for n in self.index if not any(n == p or n.startswith(p.rstrip("/") + "/") for p in exclude)}
        files = {name: (dict(sha256=digest(actual[name][0]), git_mode=actual[name][1],
                            executable=bool((self.root / name).stat().st_mode & 0o111)) if name in actual else None)
                 for name in sorted(names)}
        return dict(files=files, digest=digest(files))

    def tree(self, ref):
        if ref == "HEAD":
            ref = self._head
        return self.store["commits"][ref]["tree"] if ref in self.store["commits"] else ref

    def _tree(self, ref):
        return self.store["trees"][self.tree(ref)]

    def tracked(self, ref):
        return set(self._tree(ref))

    def _save_tree(self, files):
        tree = identifier(files)
        self.store["trees"][tree] = deepcopy(files)
        return tree

    def tree_for_paths(self, paths, base):
        files = deepcopy(self._tree(base))
        for name in paths:
            path = contained(self.root, name)
            if path.is_file():
                mode = self.index.get(name, (None, "100644"))[1] if os.name == "nt" else ("100755" if path.stat().st_mode & 0o111 else "100644")
                files[name] = (path.read_bytes(), mode)
            else:
                files.pop(name, None)
        return self._save_tree(files)

    def content(self, ref, path, filtered=False):
        files = self.index if ref == "" else self._tree(ref)
        return files.get(path, (b"", "100644"))[0]

    def _history(self):
        sha = self._head
        while sha:
            yield sha
            sha = self.store["commits"][sha]["parent"]

    def commit_info(self, sha):
        return {**self.store["commits"][sha], "reachable": sha in set(self._history())}

    def find_commits(self, marker):
        return [sha for sha in self._history() if marker in self.store["commits"][sha]["message"]]

    def commit_tree(self, tree, message):
        record = dict(tree=tree, parent=self._head, message=message)
        sha = identifier(record)
        self.store["commits"][sha] = record
        self._head = sha
        return sha

    def reset_paths(self, sha, paths):
        for path in paths:
            if path in self._tree(sha):
                self.index[path] = self._tree(sha)[path]
            else:
                self.index.pop(path, None)
            self.conflicts.discard(path)

    def create_worktree(self, path, base):
        path = Path(path).resolve()
        require(not path.exists(), "git_failed", "Worktree already exists")
        path.mkdir(parents=True)
        repo = MemoryRepository(self.factory, path, self.store, base)
        repo._write(self._tree(base))
        (path / ".git").write_text("test worktree")
        self.store["worktrees"].add(path)
        self.factory.repos[path] = repo

    def remove_worktree(self, path):
        path = Path(path).resolve()
        require(path != self.root and path in self.store["worktrees"], "git_failed", "Unregistered task worktree")
        shutil.rmtree(path)
        self.store["worktrees"].remove(path)

    def worktree(self, path):
        path = Path(path).resolve()
        if path in self.store["worktrees"]:
            repo = self.factory.repos[path]
            return dict(head=repo.head(), detached=repo.branch() is None)
        return None

    @staticmethod
    def _patch(before, after):
        if before == after:
            return b""
        changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
        encode = lambda files: {n: [data.hex(), mode] for n, (data, mode) in files.items() if n in changed}
        return json.dumps(dict(before=encode(before), after=encode(after)), sort_keys=True).encode()

    def diff_trees(self, base, tree):
        return self._patch(self._tree(base), self._tree(tree))

    def index_patch(self, full=False):
        return self._patch(self._tree("HEAD"), self.index)

    def changed_index_paths(self, base):
        before = self._tree(base)
        return {n for n in set(before) | set(self.index) if before.get(n) != self.index.get(n)}

    def dirty(self, include_ignored=False):
        return bool(self.conflicts or self.index != self._tree("HEAD") or self._files(include_ignored=include_ignored) != self.index)

    def inspect(self, exclude=()):
        require(not self.conflicts, "unmerged_index", "Resolve the existing Git conflict before execution")
        def included(files):
            return {name: value for name, value in files.items()
                    if not any(name == prefix or name.startswith(prefix.rstrip("/") + "/") for prefix in exclude)}
        actual, base, index = included(self._files()), included(self._tree("HEAD")), included(self.index)
        dirty = sorted(n for n in set(base) | set(actual) | set(index)
                       if base.get(n) != index.get(n) or index.get(n) != actual.get(n))
        return dict(head=self.head(), branch=self.branch(), dirty_paths=dirty,
                    index_patch=self._patch(base, index).decode(), working_patch=self._patch(index, actual).decode(),
                    status="" if not dirty else "\0".join(dirty) + "\0")

    def _merge(self, current, patch):
        if not artifact_bytes(patch):
            return deepcopy(current), set()
        data = json.loads(artifact_bytes(patch))
        decode = lambda files: {n: (bytes.fromhex(v[0]), v[1]) for n, v in files.items()}
        before, after = decode(data["before"]), decode(data["after"])
        result, conflicts = deepcopy(current), set()
        for name in set(before) | set(after):
            old, new, actual = before.get(name), after.get(name), current.get(name)
            if old == new:
                continue
            if actual not in (old, new):
                new = merge_file(old, actual, new)
                if new is None:
                    conflicts.add(name)
                    continue
            if new is None:
                result.pop(name, None)
            else:
                result[name] = new
        return result, conflicts

    def preview_patch(self, base, patch):
        merged, conflicts = self._merge(self._tree(base), patch)
        return None if conflicts else self._save_tree(merged)

    def _write(self, files, previous=()):
        for name in set(previous) - set(files):
            (self.root / name).unlink(missing_ok=True)
        for name, (data, mode) in files.items():
            path = contained(self.root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if mode == "100755" else 0o644)

    def apply_patch(self, patch):
        merged, conflicts = self._merge(self.index, patch)
        actual = self._files(include_ignored=True)
        for name in set(merged) | set(self.index):
            if merged.get(name) != self.index.get(name):
                require(actual.get(name) == self.index.get(name), "git_failed", "Local changes would be overwritten")
        changed = {name for name in set(merged) | set(self.index) if merged.get(name) != self.index.get(name)}
        self._write({name: merged[name] for name in changed if name in merged}, changed)
        self.index = merged
        self.conflicts = conflicts
        require(not conflicts, "git_failed", "Transfer conflict")

    def reverse_applicable(self, patch):
        if not artifact_bytes(patch):
            return True
        data = json.loads(artifact_bytes(patch))
        actual = self._files()
        for name in set(data["before"]) | set(data["after"]):
            if data["before"].get(name) != data["after"].get(name):
                value = data["after"].get(name)
                if actual.get(name) != ((bytes.fromhex(value[0]), value[1]) if value else None):
                    return False
        return True

    # Test arrangement helpers; not part of the execution interface.
    def stage(self, paths):
        actual = self._files(include_ignored=True)
        for path in paths:
            names = {n for n in set(actual) | set(self.index) if path == "." or n == path or n.startswith(path.rstrip("/") + "/")}
            for name in names:
                if name in actual:
                    self.index[name] = actual[name]
                else:
                    self.index.pop(name, None)
                self.conflicts.discard(name)

    def commit_staged(self, message):
        return self.commit_tree(self._save_tree(self.index), message)
