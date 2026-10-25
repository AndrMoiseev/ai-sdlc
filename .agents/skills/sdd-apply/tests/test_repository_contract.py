"""The execution interface's observable contract, shared by both implementations."""
from pathlib import Path

import pytest

from lib.common import Rejected
from lib.repository import repository
from repository_support import stage, commit, set_mode


pytestmark = pytest.mark.parametrize("implementation", [
    "memory", pytest.param("git", marks=pytest.mark.native_git),
])


def test_owned_commit_preserves_foreign_index_and_working_bytes(project, implementation):
    repo = repository(project)
    parent = repo.head()
    (project / "foreign.txt").write_bytes(b"staged")
    stage(project, "foreign.txt")
    (project / "foreign.txt").write_bytes(b"unstaged")
    (project / "owned.bin").write_bytes(b"\0\xffowned")
    index = repo.index_patch()
    tree = repo.tree_for_paths(["owned.bin"], parent)
    assert repo.index_patch() == index and repo.head() == parent
    sha = repo.commit_tree(tree, "TASK-one\n\nunique-operation")
    assert repo.content(sha, "owned.bin") == b"\0\xffowned"
    assert "foreign.txt" not in repo.tracked(sha)
    assert repo.content("", "foreign.txt") == b"staged"
    assert (project / "foreign.txt").read_bytes() == b"unstaged"
    assert repo.commit_info(sha) == dict(parent=parent, tree=tree,
                                        message="TASK-one\n\nunique-operation", reachable=True)
    assert repo.find_commits("unique-operation") == [sha]
    repo.reset_paths(sha, ["owned.bin"])
    assert repo.changed_index_paths(sha) == {"foreign.txt"}


def test_snapshot_tracks_deletions_modes_and_ignored_owned_files(project, implementation):
    repo = repository(project)
    (project / "check.py").chmod(0o755)
    set_mode(project, "check.py", True)
    (project / ".gitignore").write_bytes(b"ignored.txt\n")
    (project / "ignored.txt").write_bytes(b"include explicitly")
    (project / "sdd/changes/demo/proposal.md").unlink()
    assert "ignored.txt" not in repo.snapshot()["files"]
    snapshot = repo.snapshot(exclude=["sdd/changes/demo/review"], include=["ignored.txt"])
    assert snapshot["files"]["check.py"]["git_mode"] == "100755"
    assert snapshot["files"]["sdd/changes/demo/proposal.md"] is None
    assert snapshot["files"]["ignored.txt"]
    assert not any(name.startswith("sdd/changes/demo/review/") for name in snapshot["files"])
    assert repo.dirty(include_ignored=True)


def test_worktrees_and_binary_transfer_keep_unrelated_staged_data(project, tmp_path, implementation):
    repo = repository(project)
    stage(project, "check.py")  # Refresh the copied fixture's index stat data.
    base = repo.head()
    path = tmp_path / "task tree"
    repo.create_worktree(path, base)
    task = repository(path)
    assert repo.worktree(path) == dict(head=base, detached=True)
    assert repo.worktree(tmp_path / "task") is None
    assert task.branch() is None and task.head() == base
    (path / "result.bin").write_bytes(b"\x00\xffresult")
    set_mode(path, "check.py", True)
    tree = task.tree_for_paths(["result.bin", "check.py"], base)
    patch = tmp_path / "transfer.patch"
    patch.write_bytes(task.diff_trees(base, tree))
    if implementation == "git":
        assert b"GIT binary patch" in patch.read_bytes()
        assert b"new mode 100755" in patch.read_bytes()
    (project / "foreign.txt").write_bytes(b"staged")
    stage(project, "foreign.txt")
    (project / "foreign.txt").write_bytes(b"unstaged")
    before = repo.index_patch()
    assert repo.preview_patch(base, patch) == tree
    assert repo.index_patch() == before and not (project / "result.bin").exists()
    repo.apply_patch(patch)
    assert (project / "result.bin").read_bytes() == b"\x00\xffresult"
    assert repo.snapshot()["files"]["check.py"]["git_mode"] == "100755"
    assert repo.content("", "foreign.txt") == b"staged"
    assert (project / "foreign.txt").read_bytes() == b"unstaged"
    assert repo.reverse_applicable(patch)
    repo.remove_worktree(path)
    assert not path.exists() and repo.worktree(path) is None


@pytest.mark.parametrize("conflict", [False, True])
def test_preview_and_apply_report_merge_outcome_without_losing_source(project, tmp_path, implementation, conflict):
    repo = repository(project)
    initial = b"one\ntwo\nthree\nfour\n"
    (project / "merge.txt").write_bytes(initial)
    stage(project, "merge.txt")
    base = commit(project, "base")
    path = tmp_path / "task"
    repo.create_worktree(path, base)
    task = repository(path)
    (path / "merge.txt").write_bytes(initial.replace(b"two", b"task"))
    patch = tmp_path / "change.patch"
    patch.write_bytes(task.diff_trees(base, task.tree_for_paths(["merge.txt"], base)))
    (project / "merge.txt").write_bytes(initial.replace(b"two" if conflict else b"four", b"external"))
    stage(project, "merge.txt")
    head = commit(project, "concurrent")
    before = repo.snapshot()
    expected = repo.preview_patch(head, patch)
    assert repo.snapshot() == before and repo.head() == head
    if conflict:
        assert expected is None
        with pytest.raises(Rejected):
            repo.apply_patch(patch)
        assert repo.has_conflicts()
        (project / "merge.txt").write_bytes(b"resolved\n")
        stage(project, "merge.txt")
        assert not repo.has_conflicts()
    else:
        assert expected is not None
        repo.apply_patch(patch)
        assert repo.tree_for_paths(["merge.txt"], head) == expected
        assert (project / "merge.txt").read_bytes() == b"one\ntask\nthree\nexternal\n"
    assert (path / "merge.txt").read_bytes() == initial.replace(b"two", b"task")


def test_empty_transfer_and_owned_deletion_preserve_index(project, tmp_path, implementation):
    repo = repository(project)
    base = repo.head()
    (project / "check.py").unlink()
    (project / "foreign.txt").write_bytes(b"staged")
    stage(project, "foreign.txt")
    index = repo.index_patch()
    tree = repo.tree_for_paths(["check.py", "not-created.txt"], base)
    assert "check.py" not in repo.tracked(tree)
    assert repo.index_patch() == index
    patch = tmp_path / "empty.patch"
    patch.write_bytes(repo.diff_trees(base, repo.tree(base)))
    assert patch.read_bytes() == b""
    assert repo.preview_patch(base, patch) == repo.tree(base)
    assert repo.index_patch() == index
