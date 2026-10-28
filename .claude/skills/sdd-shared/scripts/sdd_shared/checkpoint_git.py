"""Git boundary for checkpoints; never resets files or bypasses hooks."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
import subprocess
import tempfile


class GitError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def parse_status(data):
    """Parse porcelain v1 -z, retaining both rename paths and arbitrary names."""
    records = iter(data.split(b"\0"))
    changes = []
    for record in records:
        if not record:
            continue
        status = record[:2].decode("ascii")
        change = {"status": status, "path": os.fsdecode(record[3:])}
        if "R" in status or "C" in status:
            change["original_path"] = os.fsdecode(next(records))
        changes.append(change)
    return changes


class Git:
    def __init__(self, project_root):
        self.root = Path(project_root).resolve()
        self.root = Path(self.run("rev-parse", "--show-toplevel").strip())
        directory = self.run("rev-parse", "--absolute-git-dir").strip()
        self.git_dir = Path(directory).resolve()
        identity = os.path.normcase(os.path.realpath(directory))
        self.worktree_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        self.oid_length = 64 if self.run("rev-parse", "--show-object-format").strip() == "sha256" else 40

    def command(self, *args, env=None, input=None):
        environment = os.environ.copy()
        # Ambient Git overrides must not redirect operations to a different index/repo.
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            environment.pop(key, None)
        environment["GIT_OPTIONAL_LOCKS"] = "0"
        environment["GIT_LITERAL_PATHSPECS"] = "1"
        environment.update(env or {})
        try:
            return subprocess.run(["git", "-C", str(self.root), *args], input=input,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=environment, shell=False)
        except FileNotFoundError as exc:
            raise GitError("git_unavailable", "Git executable or project directory is unavailable") from exc
        except OSError as exc:
            raise GitError("git_error", str(exc)) from exc

    def run(self, *args, env=None, input=None):
        result = self.command(*args, env=env, input=input)
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            code = "not_repository" if "not a git repository" in message else "git_error"
            raise GitError(code, message)
        return result.stdout.decode("utf-8", errors="surrogateescape")

    def head(self):
        result = self.command("rev-parse", "--verify", "HEAD")
        return result.stdout.decode().strip() if result.returncode == 0 else None

    def accepted(self, ref):
        symbolic = self.command("symbolic-ref", "-q", ref)
        if symbolic.returncode == 0:
            raise GitError("invalid_checkpoint_ref", "Checkpoint reference must be direct, not symbolic")
        result = self.command("show-ref", "--verify", "--quiet", ref)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise GitError("invalid_checkpoint_ref", result.stderr.decode(errors="replace"))
        oid = self.run("rev-parse", "--verify", ref).strip()
        if self.run("cat-file", "-t", oid).strip() != "commit":
            raise GitError("invalid_checkpoint_ref", "Checkpoint reference does not identify a commit")
        return oid

    def commit_exists(self, oid):
        if not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{%d}" % self.oid_length, oid):
            return False
        result = self.command("cat-file", "-t", oid)
        return result.returncode == 0 and result.stdout.strip() == b"commit"

    def changes(self):
        indexed = self.run("ls-files", "-v", "-z").split("\0")
        hidden = [record[2:] for record in indexed
                  if record and (record[0].islower() or record[0] == "S")]
        if hidden:
            raise GitError("unsupported_index_flags",
                           "Cannot verify tracked files with assume-unchanged/skip-worktree flags: "
                           + repr(hidden) + ". Resolve these flags explicitly before retrying; files and flags were preserved.")
        result = self.command("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
        if result.returncode:
            raise GitError("git_error", result.stderr.decode(errors="replace"))
        return parse_status(result.stdout)

    def operation_in_progress(self):
        for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer", "BISECT_START"):
            if (self.git_dir / name).exists():
                return True
        return False

    def capture(self):
        changes = self.changes()
        paths = sorted({change[key] for change in changes for key in ("path", "original_path") if key in change})
        # The temporary index starts from HEAD: the real user's index stays intact.
        with tempfile.TemporaryDirectory(prefix="sdd-checkpoint-") as directory:
            env = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
            self.run("read-tree", "HEAD", env=env)
            if paths:
                self.stage(paths, env=env)
            tree = self.run("write-tree", env=env).strip()
        return {"paths": paths, "tree": tree, "index_tree": self.run("write-tree").strip()}

    def stage(self, paths, env=None):
        tracked = self.run("ls-files", "--cached", "-z", env=env).split("\0")
        # A staged rename/deletion already removed its source from the real index.
        # Keep it in the reviewed path set, but do not submit a nonexistent pathspec.
        paths = [path for path in paths if path in tracked or os.path.lexists(self.root / path)]
        if not paths:
            return
        payload = b"\0".join(os.fsencode(path) for path in paths) + b"\0"
        self.run("add", "--all", "--pathspec-from-file=-", "--pathspec-file-nul", env=env, input=payload)

    def update(self, ref, new, old, expected_head, message):
        # --no-deref refuses to follow a checkpoint made symbolic during the race.
        # Verify HEAD in the same transaction as the checkpoint CAS.
        old = old or "0" * self.oid_length
        transaction = f"start\nverify HEAD {expected_head}\nupdate {ref} {new} {old}\nprepare\ncommit\n"
        self.run("update-ref", "--no-deref", "--create-reflog", "-m", message,
                 "--stdin", input=transaction.encode("utf-8"))

    def commit(self, message):
        return self.command("commit", "-m", message)

    def commit_matches(self, oid, parent, tree):
        actual = self.run("rev-list", "--parents", "-n", "1", oid).strip().split()
        return actual == [oid, parent] and self.run("rev-parse", f"{oid}^{{tree}}").strip() == tree

    def difference(self, accepted, head):
        return self.run("diff", "--stat", accepted, head, "--").strip()
