"""Checkpoint policy is tested through a fake; one Git scenario verifies plumbing."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdd_shared import checkpoints as cp
from sdd_shared.checkpoint_git import Git, GitError, parse_status

BASE = "a" * 40
NEW = "b" * 40
TREE = "c" * 40
DECISION = dict(id="USER-1", response="Accept this state", source="conversation", date="2026-10-27", accepted_commit=BASE)
INSTRUCTION = dict(text="Implement the assigned task", source="conversation USER-2")


class FakeGit:
    worktree_key = "worktree"

    def __init__(self):
        self.current = BASE
        self.ref = BASE
        self.changed = []
        self.active_operation = False
        self.reviewed = dict(paths=[], tree=TREE, index_tree=TREE)
        self.commit_exit = 0
        self.commit_tree_matches = True
        self.cas_failure = False
        self.after_update_dirty = False
        self.after_commit_dirty = False
        self.staged = []
        self.commits = 0
        self.updates = 0

    def head(self):
        return self.current

    def accepted(self, ref):
        return self.ref

    def changes(self):
        return self.changed

    def operation_in_progress(self):
        return self.active_operation

    def capture(self):
        return self.reviewed.copy()

    def stage(self, paths):
        self.staged = paths

    def run(self, *args):
        assert args == ("write-tree",)
        return TREE

    def commit(self, message):
        self.commits += 1
        if not self.commit_exit:
            self.current = NEW
            if not self.after_commit_dirty:
                self.changed = []
        return SimpleNamespace(returncode=self.commit_exit, stderr=b"hook failed")

    def commit_matches(self, oid, parent, tree):
        assert (oid, parent, tree) == (NEW, BASE, TREE)
        return self.commit_tree_matches

    def update(self, ref, new, old, expected_head, message):
        self.updates += 1
        assert old == self.ref
        assert expected_head == self.current
        if self.cas_failure:
            raise GitError("git_error", "CAS rejected")
        self.ref = new
        if self.after_update_dirty:
            self.changed = [{"status": " M", "path": "external.txt"}]

    def difference(self, old, new):
        return "tree difference"


@pytest.fixture
def fake(monkeypatch):
    git = FakeGit()
    monkeypatch.setattr(cp, "Git", lambda project: git)
    return git


@pytest.mark.parametrize("head,accepted,changes,active,status", [
    (None, None, [], False, "unborn_head"),
    (BASE, None, [], False, "acceptance_required"),
    (BASE, BASE, [], False, "ready"),
    (NEW, BASE, [], False, "head_mismatch"),
    (BASE, BASE, [{"status": "??"}], False, "dirty"),
    (BASE, BASE, [{"status": "UU"}], False, "git_operation_in_progress"),
    (BASE, BASE, [], True, "git_operation_in_progress"),
])
def test_classification(head, accepted, changes, active, status):
    assert cp.classify(head, accepted, changes, active) == status


def test_nul_status_preserves_unicode_newlines_and_rename_sides():
    raw = "R  новое имя\n.txt\0старое имя.txt\0 D removed\0?? extra\0".encode()
    assert parse_status(raw) == [dict(status="R ", path="новое имя\n.txt", original_path="старое имя.txt"),
                                 dict(status=" D", path="removed"), dict(status="??", path="extra")]


@pytest.mark.parametrize("tag", ["h", "S", "s"])
def test_git_status_refuses_hidden_index_flags_before_trusting_status(monkeypatch, tag):
    adapter = object.__new__(Git)
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        assert args == ("ls-files", "-v", "-z")
        return SimpleNamespace(returncode=0, stdout=f"{tag} имя\nfile.txt\0".encode(), stderr=b"")

    monkeypatch.setattr(adapter, "command", command)
    with pytest.raises(GitError) as error:
        adapter.changes()
    assert error.value.code == "unsupported_index_flags"
    assert "имя" in str(error.value)
    assert calls == [("ls-files", "-v", "-z")]


def test_regular_index_flags_allow_status_observation(monkeypatch):
    adapter = object.__new__(Git)
    outputs = iter([b"H tracked.txt\0", b" M tracked.txt\0"])
    monkeypatch.setattr(adapter, "command", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=next(outputs), stderr=b""))
    assert adapter.changes() == [{"status": " M", "path": "tracked.txt"}]


def test_inspect_missing_ref_is_read_only(fake):
    fake.ref = None
    result = cp.inspect(".", "change", "example")
    assert result["status"] == "acceptance_required"
    assert result["exit_code"] == 0
    assert fake.updates == fake.commits == 0
    assert cp.inspect(".", "refactoring", "example")["checkpoint_ref"] != result["checkpoint_ref"]


@pytest.mark.parametrize("mutation,expected", [
    ("dirty", "dirty"), ("head", "concurrent_change"),
    ("ref", "concurrent_change"), ("operation", "git_operation_in_progress"),
    ("decision", "decision_required"),
])
def test_accept_rejects_unconfirmed_or_changed_state(fake, mutation, expected):
    decision = DECISION.copy()
    if mutation == "dirty":
        fake.changed = [{"status": "??", "path": "file"}]
    elif mutation == "head":
        fake.current = NEW
    elif mutation == "ref":
        fake.ref = None
    elif mutation == "operation":
        fake.active_operation = True
    else:
        decision.pop("source")
    result = cp.accept(".", "change", "example", BASE, BASE, decision)
    assert result["status"] == expected
    assert fake.updates == fake.commits == 0


def test_accept_missing_ref_and_repeated_acceptance(fake):
    fake.ref = None
    result = cp.accept(".", "change", "example", BASE, None, DECISION)
    assert result["status"] == "accepted"
    assert result["ref_updated"] is True
    repeated = cp.accept(".", "change", "example", BASE, BASE, DECISION)
    assert repeated["status"] == "unchanged"
    assert fake.updates == 1
    assert fake.commits == 0


def test_accept_post_update_race_reports_written_ref(fake):
    fake.ref = None
    fake.after_update_dirty = True
    result = cp.accept(".", "change", "example", BASE, None, DECISION)
    assert result["status"] == "concurrent_change"
    assert result["ref_updated"] is True
    assert fake.ref == BASE


def create(fake, instruction=INSTRUCTION, reviewed=None):
    return cp.create(".", "change", "example", BASE, BASE,
                     reviewed if reviewed is not None else fake.capture(), instruction, "checkpoint")


def test_create_requires_instruction_separate_from_acceptance(fake):
    assert create(fake, instruction=DECISION)["status"] == "instruction_required"
    assert fake.commits == 0


def test_create_no_changes_is_unchanged(fake):
    assert create(fake)["status"] == "unchanged"
    assert fake.commits == fake.updates == 0


@pytest.mark.parametrize("field,value", [("tree", NEW), ("paths", ["unknown"]), ("index_tree", NEW)])
def test_create_detects_reviewed_content_paths_and_index_changes(fake, field, value):
    reviewed = fake.capture()
    reviewed[field] = value
    assert create(fake, reviewed=reviewed)["status"] == "changes_changed"
    assert fake.staged == []
    assert fake.commits == 0


@pytest.mark.parametrize("failure,status,created,updated", [
    (None, "created", NEW, True),
    ("hook", "commit_failed", None, False),
    ("tree", "commit_created_unaccepted", NEW, False),
    ("dirty", "commit_created_unaccepted", NEW, False),
    ("cas", "commit_created_unaccepted", NEW, False),
    ("post", "concurrent_change", NEW, True),
])
def test_creation_failure_boundaries_preserve_result(fake, failure, status, created, updated):
    fake.changed = [{"status": " M", "path": "file"}]
    fake.reviewed["paths"] = ["file"]
    fake.commit_exit = 1 if failure == "hook" else 0
    fake.commit_tree_matches = failure != "tree"
    fake.after_commit_dirty = failure == "dirty"
    fake.cas_failure = failure == "cas"
    fake.after_update_dirty = failure == "post"
    result = create(fake)
    assert result["status"] == status
    assert result["created_commit"] == created
    assert result["ref_updated"] is updated
    assert fake.ref == (NEW if updated else BASE)
    assert fake.staged == ["file"]


def test_real_git_checkpoint_index_hooks_and_cas(tmp_path):
    # Real risk: Git's NUL pathspec/index and hook/CAS semantics cannot be proven
    # by a fake. One repository exercises these boundaries without a scenario matrix.
    def git(*args):
        result = subprocess.run(["git", "-C", str(tmp_path), *args], shell=False,
                                capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Checkpoint test")
    git("config", "user.email", "checkpoint@example.invalid")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "old.txt").write_text("original\n", encoding="utf-8")
    (tmp_path / "remove.txt").write_text("remove\n", encoding="utf-8")
    git("add", "--", "old.txt", "remove.txt")
    git("commit", "-qm", "initial")
    base = git("rev-parse", "HEAD")
    decision = dict(DECISION, accepted_commit=base)
    accepted = cp.accept(tmp_path, "change", "example", base, None, decision)
    assert accepted["status"] == "accepted", accepted
    # Reuse this native fixture: only real Git proves that the index flag hides
    # an edit from porcelain and that inspection leaves the flag and bytes intact.
    git("update-index", "--assume-unchanged", "--", "old.txt")
    (tmp_path / "old.txt").write_text("hidden edit\n", encoding="utf-8")
    assert git("status", "--porcelain") == ""
    blocked = cp.inspect(tmp_path, "change", "example")
    assert blocked["status"] == "unsupported_index_flags"
    assert blocked["exit_code"] == 2
    assert git("ls-files", "-v", "--", "old.txt") == "h old.txt"
    assert (tmp_path / "old.txt").read_text(encoding="utf-8") == "hidden edit\n"
    assert git("rev-parse", accepted["checkpoint_ref"]) == base
    git("update-index", "--no-assume-unchanged", "--", "old.txt")
    (tmp_path / "old.txt").write_text("original\n", encoding="utf-8")
    git("mv", "--", "old.txt", "новое имя.txt")
    (tmp_path / "remove.txt").unlink()
    (tmp_path / "extra file.txt").write_text("new\n", encoding="utf-8")
    reviewed = cp.capture_changes(tmp_path)
    assert set(reviewed["paths"]) == {"old.txt", "новое имя.txt", "remove.txt", "extra file.txt"}
    (tmp_path / "extra file.txt").write_text("unreviewed\n", encoding="utf-8")
    rejected = cp.create(tmp_path, "change", "example", base, base, reviewed, INSTRUCTION, "checkpoint")
    assert rejected["status"] == "changes_changed"
    (tmp_path / "extra file.txt").write_text("new\n", encoding="utf-8")
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    rejected = cp.create(tmp_path, "change", "example", base, base, reviewed, INSTRUCTION, "checkpoint")
    assert rejected["status"] == "commit_failed", rejected
    assert git("rev-parse", "HEAD") == base
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    reviewed = cp.capture_changes(tmp_path)  # The refused hook leaves the prepared index intact.
    created = cp.create(tmp_path, "change", "example", base, base, reviewed, INSTRUCTION, "checkpoint")
    assert created["status"] == "created", created
    assert git("status", "--porcelain") == ""
    assert git("rev-parse", accepted["checkpoint_ref"]) == created["created_commit"]
    adapter = Git(tmp_path)
    with pytest.raises(GitError):
        adapter.update(accepted["checkpoint_ref"], base, base, created["created_commit"], "stale")
    assert git("rev-parse", accepted["checkpoint_ref"]) == created["created_commit"]
