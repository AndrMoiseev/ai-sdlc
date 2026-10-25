"""Native Git implementation. Command syntax and index plumbing stay here."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import tempfile

from .common import contained, digest, require


class GitRepository:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def _run(self, *args, env=None, check=True):
        result = subprocess.run(["git", "-C", str(self.root), *map(str, args)],
                                capture_output=True, env=env, shell=False)
        require(not check or result.returncode == 0, "git_failed", result.stderr.decode("utf-8", "replace"))
        return result

    def _text(self, *args, **kwargs):
        return self._run(*args, **kwargs).stdout.decode("utf-8", "replace").strip()

    @contextmanager
    def _index(self, base):
        with tempfile.TemporaryDirectory(prefix="sdd-apply-index-") as temp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(temp) / "index")}
            self._run("read-tree", base, env=env)
            yield env

    def head(self):
        return self._text("rev-parse", "HEAD")

    def branch(self):
        return self._text("symbolic-ref", "--quiet", "--short", "HEAD", check=False) or None

    def has_conflicts(self):
        return bool(self._text("ls-files", "--unmerged"))

    def inspect(self, exclude=()):
        head = self.head()
        require(not self.has_conflicts(), "unmerged_index", "Resolve the existing Git conflict before execution")
        branch = self._text("symbolic-ref", "--quiet", "--short", "HEAD")
        self._run("var", "GIT_AUTHOR_IDENT")
        self._run("var", "GIT_COMMITTER_IDENT")
        dirty = set()
        pathspec = ("--", ".", *(f":(top,exclude,literal){name}" for name in exclude))
        for args in (("diff", "--name-only", "--cached", "-z"), ("diff", "--name-only", "-z"),
                     ("ls-files", "--others", "--exclude-standard", "-z")):
            dirty.update(filter(None, self._run(*args, *pathspec).stdout.decode("utf-8").split("\0")))
        return dict(head=head, branch=branch, dirty_paths=sorted(dirty),
                    index_patch=self._run("diff", "--binary", "--cached", *pathspec).stdout.decode("utf-8", "replace"),
                    working_patch=self._run("diff", "--binary", *pathspec).stdout.decode("utf-8", "replace"),
                    status=self._run("status", "--porcelain=v1", "-z", *pathspec).stdout.decode("utf-8"))

    def snapshot(self, exclude=(), include=()):
        records = self._run("ls-files", "-t", "--stage", "--others", "--exclude-standard", "-z").stdout.decode("utf-8").split("\0")
        names, modes = set(), {}
        for record in filter(None, records):
            name = record[2:]
            if not record.startswith("? "):
                meta, name = name.split("\t", 1)
                mode, _, stage = meta.split()
                require(stage == "0", "unmerged_index", name)
                modes[name] = mode
            names.add(name)
        files = {}
        for name in sorted(names | set(include)):
            if any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclude):
                continue
            require(not (self.root / name).is_symlink(), "unsupported_file", name)
            path = contained(self.root, name)
            require(not path.is_dir(), "unsupported_file", f"Directory/submodule is not a supported source file: {name}")
            if path.is_file():
                executable = bool(path.stat().st_mode & 0o111)
                mode = modes.get(name, "100644") if os.name == "nt" else ("100755" if executable else "100644")
                require(mode in {"100644", "100755"}, "unsupported_file", f"Unsupported Git mode {mode}: {name}")
                files[name] = dict(sha256=digest(path.read_bytes()), executable=executable, git_mode=mode)
            elif name in names:
                files[name] = None
        return dict(files=files, digest=digest(files))

    def tree(self, ref):
        return self._text("rev-parse", ref + "^{tree}")

    def tracked(self, ref):
        return set(filter(None, self._run("ls-tree", "-r", "--name-only", "-z", ref).stdout.decode("utf-8").split("\0")))

    def tree_for_paths(self, paths, base):
        present = [p for p in paths if p in self.tracked(base) or (self.root / p).exists()]
        if not present:
            return self.tree(base)
        with self._index(base) as env:
            self._run("add", "--force", "--all", "--", *present, env=env)
            snapshot = self.snapshot(include=present)
            for path in present:
                metadata = snapshot["files"].get(path)
                if metadata:
                    self._run("update-index", "--chmod=" + ("+x" if metadata["git_mode"] == "100755" else "-x"), "--", path, env=env)
            return self._text("write-tree", env=env)

    def content(self, ref, path, filtered=False):
        args = ("cat-file", "--filters") if filtered else ("show",)
        return self._run(*args, ref + ":" + path, check=False).stdout

    def commit_info(self, sha):
        return dict(tree=self.tree(sha), parent=self._text("rev-parse", sha + "^"),
                    message=self._text("show", "-s", "--format=%B", sha),
                    reachable=sha in self._text("rev-list", "HEAD").splitlines())

    def find_commits(self, marker):
        return self._text("log", "--format=%H", "--fixed-strings", "--grep", marker).splitlines()

    def commit_tree(self, tree, message):
        with self._index(tree) as env:
            self._run("commit", "-m", message, env=env)
        return self.head()

    def reset_paths(self, sha, paths):
        self._run("reset", "--quiet", sha, "--", *paths)

    def create_worktree(self, path, base):
        self._run("worktree", "add", "--detach", str(path), base)

    def remove_worktree(self, path):
        self._run("worktree", "remove", "--force", str(path))

    def worktree(self, path):
        wanted = str(Path(path).resolve()).replace("\\", "/")
        entries = self._run("worktree", "list", "--porcelain", "-z").stdout.decode("utf-8").split("\0\0")
        for entry in entries:
            fields = dict(line.partition(" ")[::2] for line in entry.split("\0") if line)
            if fields.get("worktree", "").replace("\\", "/") == wanted:
                return dict(head=fields["HEAD"], detached="detached" in fields)
        return None

    def index_patch(self, full=False):
        return self._run("diff", "--cached", "--binary", *(["--full-index"] if full else [])).stdout

    def changed_index_paths(self, base):
        return set(filter(None, self._run("diff", "--cached", "--name-only", "-z", base).stdout.decode("utf-8").split("\0")))

    def dirty(self, include_ignored=False):
        return bool(self._text("status", "--porcelain", "--untracked-files=all", *(["--ignored"] if include_ignored else [])))

    def diff_trees(self, base, tree):
        return self._run("diff", "--binary", "--full-index", base, tree).stdout

    def preview_patch(self, base, patch):
        with self._index(base) as env:
            result = self._run("apply", "--cached", "--3way", str(patch), env=env, check=False) if Path(patch).stat().st_size else None
            return self._text("write-tree", env=env) if result is None or result.returncode == 0 else None

    def reverse_applicable(self, patch):
        return self._run("apply", "--reverse", "--check", str(patch), check=False).returncode == 0

    def apply_patch(self, patch):
        self._run("apply", "--3way", "--index", str(patch))
