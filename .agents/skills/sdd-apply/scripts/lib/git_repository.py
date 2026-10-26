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

    def status(self, exclude=(), include_ignored=False):
        """Use Git's index cache; retain path names, never a source-file manifest."""
        indexed = self._run("ls-files", "-v", "--stage", "-z").stdout.decode("utf-8").split("\0")
        for record in filter(None, indexed):
            tag, metadata = record[0], record[2:]
            mode = metadata.split(" ", 1)[0]
            require(not tag.islower() and tag != "S" and mode in {"100644", "100755"}, "unsupported_index",
                    "Clear assume-unchanged/skip-worktree flags; links and submodules need an explicit verification contract")
        pathspec = ("--", ".", *(f":(top,exclude,literal){name}" for name in exclude))
        records = self._run("-c", "core.fsmonitor=false", "-c", "core.ignoreStat=false",
                            *(["-c", "core.fileMode=true"] if os.name != "nt" else []),
                            "status", "--porcelain=v2", "--branch", "--no-renames", "-z",
                            "--untracked-files=all", "--ignore-submodules=none", *(["--ignored"] if include_ignored else []),
                            *pathspec).stdout.decode("utf-8").split("\0")
        dirty, untracked, ignored = [], [], []
        head, branch = None, None
        for record in filter(None, records):
            if record.startswith("# branch.oid "):
                head = record.removeprefix("# branch.oid ")
                continue
            if record.startswith("# branch.head "):
                branch = record.removeprefix("# branch.head ")
                if branch == "(detached)":
                    branch = None
                continue
            if record.startswith("# "):
                continue
            code = record[0]
            require(code in {"1", "u", "?", "!"}, "git_status", "Unexpected status record")
            name = record.split(" ", 8)[8] if code == "1" else record.split(" ", 10)[10] if code == "u" else record[2:]
            if code == "!":
                ignored.append(name)
            else:
                dirty.append(name)
                if code == "?":
                    untracked.append(name)
        require(head and head != "(initial)", "git_failed", "Repository has no HEAD commit")
        return dict(head=head, branch=branch, dirty_paths=sorted(dirty),
                    untracked_paths=sorted(untracked), ignored_paths=sorted(ignored))

    def changed_paths(self, base, target="HEAD"):
        return set(filter(None, self._run("diff", "--no-renames", "--name-only", "-z", base, target).stdout.decode("utf-8").split("\0")))

    def inspect(self, exclude=()):
        require(not self.has_conflicts(), "unmerged_index", "Resolve the existing Git conflict before execution")
        status = self.status(exclude)
        require(status["branch"], "git_failed", "Execution requires a named branch")
        self._run("var", "GIT_AUTHOR_IDENT")
        self._run("var", "GIT_COMMITTER_IDENT")
        return {key: status[key] for key in ("head", "branch", "dirty_paths")}

    def tree(self, ref):
        return self._text("rev-parse", ref + "^{tree}")

    def tracked(self, ref):
        return set(filter(None, self._run("ls-tree", "-r", "--name-only", "-z", ref).stdout.decode("utf-8").split("\0")))

    def tree_for_paths(self, paths, base):
        tracked = self.tracked(base)
        present = [p for p in paths if p in tracked or (self.root / p).exists()]
        if not present:
            return self.tree(base)
        with self._index(base) as env:
            self._run("add", "--force", "--all", "--", *present, env=env)
            if os.name == "nt":
                records = self._run("ls-files", "--stage", "-z", "--", *present).stdout.decode("utf-8").split("\0")
                for record in filter(None, records):
                    metadata, name = record.split("\t", 1)
                    mode, _, stage = metadata.split()
                    require(stage == "0", "unmerged_index", name)
                    if (self.root / name).is_file():
                        self._run("update-index", "--chmod=" + ("+x" if mode == "100755" else "-x"), "--", name, env=env)
            return self._text("write-tree", env=env)

    def content(self, ref, path, filtered=False):
        args = ("cat-file", "--filters") if filtered else ("show",)
        return self._run(*args, ref + ":" + path, check=False).stdout

    def commit_info(self, sha):
        tree, _, rest = self._text("show", "-s", "--format=%T%n%P%n%B", sha).partition("\n")
        parents, _, message = rest.partition("\n")
        return dict(tree=tree, parent=parents.split()[0] if parents else None,
                    message=message.strip(),
                    reachable=self._run("merge-base", "--is-ancestor", sha, "HEAD", check=False).returncode == 0)

    def find_commits(self, marker):
        records = self._text("log", "--format=%H%x00%B%x00", "--fixed-strings", "--grep", marker).split("\0")
        return [records[index].strip() for index in range(0, len(records) - 1, 2)
                if marker in records[index + 1].splitlines()]

    def commit_tree(self, tree, message):
        with self._index(tree) as env:
            self._run("commit", "--allow-empty", "-m", message, env=env)
        return self.head()

    def reset_paths(self, sha, paths):
        self._run("reset", "--quiet", sha, "--", *paths)

    def create_worktree(self, path, base, branch=None):
        self._run("worktree", "add", *(["-b", branch] if branch else ["--detach"]), str(path), base)

    def remove_worktree(self, path):
        self._run("worktree", "remove", str(path))

    def worktree(self, path):
        wanted = str(Path(path).resolve()).replace("\\", "/")
        entries = self._run("worktree", "list", "--porcelain", "-z").stdout.decode("utf-8").split("\0\0")
        for entry in entries:
            fields = dict(line.partition(" ")[::2] for line in entry.split("\0") if line)
            if fields.get("worktree", "").replace("\\", "/") == wanted:
                result = dict(head=fields["HEAD"], detached="detached" in fields)
                if "branch" in fields:
                    result["branch"] = fields["branch"].removeprefix("refs/heads/")
                return result
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
