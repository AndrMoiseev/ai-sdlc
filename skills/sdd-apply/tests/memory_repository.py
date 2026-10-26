"""Stateful repository test implementation, with real working files for checks.

Models the execution interface, not Git command syntax. Transfer bytes are
opaque JSON; native patch syntax, hooks and filters are tested with real Git.
"""
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
    if isinstance(repo, GitRepository):
        records = repo._run("ls-files", "--stage", "-z").stdout.decode().split("\0")
        modes = {record.split("\t", 1)[1]: record.split()[0] for record in records if record}
        files = {name: (Path(root, name).read_bytes(), mode) for name, mode in modes.items()}
    else:
        files = repo._files()
    return dict(head=repo.head(), branch=repo.branch(),
                files=files)


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
        store = dict(trees={tree: dict(seed["files"])},
                     commits={seed["head"]: dict(tree=tree, parent=None, message="fixture")},
                     worktrees={root}, main_root=root, ignores=[])
        repo = MemoryRepository(self, root, store, seed["head"], seed["branch"])
        self.repos[root] = repo
        return repo


class MemoryRepository:
    def __init__(self, factory, root, store, head, branch=None):
        self.factory, self.root, self.store = factory, Path(root), store
        self._head, self._branch = head, branch
        # Tree entries are immutable (bytes, mode-string) tuples; only the maps
        # need copying to keep staging and later commits independent.
        self.index = dict(store["trees"][store["commits"][head]["tree"]])
        self.conflicts = set()
        # None selects the disk boundary. Logic scenarios supply independent
        # bytes explicitly; this is their working tree, not a filesystem cache.
        self.working_files = None

    def head(self):
        return self._head

    def branch(self):
        return self._branch

    def has_conflicts(self):
        return bool(self.conflicts)

    def _ignore_patterns(self):
        patterns = list(self.store["ignores"])
        if self.working_files is not None:
            patterns.extend(self.working_files.get(".gitignore", (b"", None))[0].decode().splitlines())
            return [pattern for pattern in patterns if pattern and not pattern.startswith("#")]
        for path in (self.root / ".gitignore", self.store["main_root"] / ".git/info/exclude"):
            if path.is_file():
                patterns.extend(path.read_text().splitlines())
        return [pattern for pattern in patterns if pattern and not pattern.startswith("#")]

    def _files(self, exclude=(), include_ignored=False):
        result = {}
        patterns = self._ignore_patterns()
        if self.working_files is not None:
            return {name: value for name, value in self.working_files.items()
                    if not any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclude)
                    and (include_ignored or name in self.index or not any(fnmatch(name, p) for p in patterns))}
        pending = [(self.root, "")]
        while pending:
            directory, prefix = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    name = prefix + entry.name
                    if entry.name == ".git" or any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclude):
                        continue
                    require(not entry.is_symlink() and not (hasattr(entry, "is_junction") and entry.is_junction()),
                            "unsupported_file", name)
                    if entry.is_dir(follow_symlinks=False):
                        pending.append((entry.path, name + "/"))
                    elif include_ignored or name in self.index or not any(fnmatch(name, pattern) for pattern in patterns):
                        mode = self.index.get(name, (None, "100644"))[1] if os.name == "nt" else ("100755" if entry.stat().st_mode & 0o111 else "100644")
                        result[name] = (Path(entry.path).read_bytes(), mode)
        return result

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
        self.store["trees"][tree] = dict(files)
        return tree

    def tree_for_paths(self, paths, base):
        files = dict(self._tree(base))
        for name in paths:
            if self.working_files is not None:
                if name in self.working_files:
                    files[name] = self.working_files[name]
                else:
                    files.pop(name, None)
                continue
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

    def create_worktree(self, path, base, branch=None):
        assert self.working_files is None, "Worktree creation requires the disk contract fixture"
        path = Path(path).resolve()
        require(not path.exists(), "git_failed", "Worktree already exists")
        path.mkdir(parents=True)
        repo = MemoryRepository(self.factory, path, self.store, base, branch)
        repo._write(self._tree(base))
        (path / ".git").write_text("test worktree")
        self.store["worktrees"].add(path)
        self.factory.repos[path] = repo

    def remove_worktree(self, path):
        assert self.working_files is None, "Worktree removal requires the disk contract fixture"
        path = Path(path).resolve()
        require(path != self.root and path in self.store["worktrees"], "git_failed", "Unregistered task worktree")
        require(not self.factory(path).dirty(), "git_failed", "Worktree contains modified or untracked files")
        shutil.rmtree(path)
        self.store["worktrees"].remove(path)

    def worktree(self, path):
        path = Path(path).resolve()
        if path in self.store["worktrees"]:
            repo = self.factory.repos[path]
            return dict(head=repo.head(), detached=repo.branch() is None,
                        **({"branch": repo.branch()} if repo.branch() else {}))
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

    def changed_paths(self, base, target="HEAD"):
        before, after = self._tree(base), self._tree(target)
        return {name for name in set(before) | set(after) if before.get(name) != after.get(name)}

    def status(self, exclude=(), include_ignored=False):
        require(not self.conflicts, "unmerged_index", "Resolve the existing Git conflict before execution")
        def included(name):
            return not any(name == prefix or name.startswith(prefix.rstrip("/") + "/") for prefix in exclude)
        actual = self._files(exclude)
        base, index = self._tree("HEAD"), self.index
        names = {name for name in set(base) | set(index) | set(actual) if included(name)}
        dirty = sorted(name for name in names if base.get(name) != index.get(name) or index.get(name) != actual.get(name))
        untracked = sorted(set(actual) - set(index))
        ignored = sorted(set(self._files(exclude, include_ignored=True)) - set(actual)) if include_ignored else []
        return dict(head=self.head(), branch=self.branch(), dirty_paths=dirty,
                    untracked_paths=untracked, ignored_paths=ignored)

    def dirty(self, include_ignored=False):
        return bool(self.conflicts or self.index != self._tree("HEAD") or self._files(include_ignored=include_ignored) != self.index)

    def inspect(self, exclude=()):
        state = self.status(exclude)
        return {name: state[name] for name in ("head", "branch", "dirty_paths")}

    def _merge(self, current, patch):
        if not artifact_bytes(patch):
            return dict(current), set()
        data = json.loads(artifact_bytes(patch))
        decode = lambda files: {n: (bytes.fromhex(v[0]), v[1]) for n, v in files.items()}
        before, after = decode(data["before"]), decode(data["after"])
        result, conflicts = dict(current), set()
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
        assert self.working_files is None, "Patch materialization requires the disk contract fixture"
        for name in set(previous) - set(files):
            (self.root / name).unlink(missing_ok=True)
        directories = {self.root}
        for name, (data, mode) in files.items():
            path = contained(self.root, name)
            if path.parent not in directories:
                path.parent.mkdir(parents=True, exist_ok=True)
                directories.add(path.parent)
            path.write_bytes(data)
            # Windows has no executable mode bit; this adapter keeps Git's
            # mode in its index. New files are already writable there.
            if os.name != "nt":
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
