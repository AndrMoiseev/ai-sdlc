"""The execution interface's observable contract, shared by both implementations."""
from pathlib import Path

import pytest

from lib.common import Rejected
from lib.repository import repository
from repository_support import stage, commit, set_mode, file_mode, write_file, read_file, remove_file


pytestmark = pytest.mark.parametrize("implementation", [
    "memory", pytest.param("git", marks=pytest.mark.native_git),
])


@pytest.fixture
def working_tree(project, implementation, monkeypatch):
    """Reuse existing Git contracts for the explicit in-memory working tree."""
    repo = repository(project)
    if implementation == "memory":
        repo.working_files = repo._files(include_ignored=True)
        # No disk fallback may make the dictionary model appear correct.
        import os
        original_scan, original_read = os.scandir, Path.read_bytes
        def scan(path):
            assert not Path(path).is_relative_to(project), "Memory working tree scanned the disk"
            return original_scan(path)
        def read(path):
            assert not path.is_relative_to(project), "Memory working tree read the disk"
            return original_read(path)
        monkeypatch.setattr(os, "scandir", scan)
        monkeypatch.setattr(Path, "read_bytes", read)
    return repo


def test_inspect_excludes_tracked_and_untracked_execution_artifacts(project, implementation, working_tree):
    path = "sdd/changes/demo/execution/state.json"
    write_file(project, path, b"initial")
    stage(project, "sdd/changes/demo/execution/state.json")
    commit(project, "saved execution")
    write_file(project, path, b"staged state")
    stage(project, "sdd/changes/demo/execution/state.json")
    write_file(project, path, b"unstaged state")
    write_file(project, "sdd/changes/demo/execution/dashboard.html", b"generated")
    write_file(project, "check.py", b"assert True")
    view = repository(project).inspect(exclude=["sdd/changes/demo/execution"])
    assert view["dirty_paths"] == ["check.py"]
    assert set(view) == {"head", "branch", "dirty_paths"}


def test_owned_commit_preserves_foreign_index_and_working_bytes(project, implementation, working_tree):
    repo = working_tree
    parent = repo.head()
    write_file(project, "foreign.txt", b"staged")
    stage(project, "foreign.txt")
    write_file(project, "foreign.txt", b"unstaged")
    write_file(project, "owned.bin", b"\0\xffowned")
    index = repo.index_patch()
    tree = repo.tree_for_paths(["owned.bin"], parent)
    assert repo.index_patch() == index and repo.head() == parent
    sha = repo.commit_tree(tree, "TASK-one\n\nunique-operation")
    assert repo.content(sha, "owned.bin") == b"\0\xffowned"
    assert "foreign.txt" not in repo.tracked(sha)
    assert repo.content("", "foreign.txt") == b"staged"
    assert read_file(project, "foreign.txt") == b"unstaged"
    assert repo.commit_info(sha) == dict(parent=parent, tree=tree,
                                        message="TASK-one\n\nunique-operation", reachable=True)
    assert repo.find_commits("unique-operation") == [sha]
    repo.reset_paths(sha, ["owned.bin"])
    assert repo.changed_index_paths(sha) == {"foreign.txt"}


def test_git_tree_retains_modes_deletions_and_explicit_ignored_owned_files(project, implementation, working_tree):
    repo = working_tree
    if implementation == "git":
        (project / "check.py").chmod(0o755)
    set_mode(project, "check.py", True)
    write_file(project, ".gitignore", b"ignored.txt\n")
    write_file(project, "ignored.txt", b"include explicitly")
    remove_file(project, "sdd/changes/demo/proposal.md")
    assert "ignored.txt" not in repo.status()["dirty_paths"]
    tree = repo.tree_for_paths(["ignored.txt", "check.py", "sdd/changes/demo/proposal.md"], repo.head())
    assert file_mode(project, "check.py") == "100755"
    assert "sdd/changes/demo/proposal.md" not in repo.tracked(tree)
    assert repo.content(tree, "ignored.txt") == b"include explicitly"
    assert repo.dirty(include_ignored=True)


def test_status_and_commit_comparison_include_each_change_kind(project, implementation, working_tree):
    repo = working_tree
    base = repo.head()
    write_file(project, ".gitignore", b"ignored.txt\n")
    stage(project, ".gitignore")
    commit(project, "Ignore generated fixture file")
    write_file(project, "ignored.txt", b"generated")
    write_file(project, "new file.txt", b"untracked")
    write_file(project, "check.py", b"staged change")
    stage(project, "check.py")
    write_file(project, "check.py", b"unstaged change")
    remove_file(project, "sdd/changes/demo/proposal.md")
    view = repo.status(include_ignored=True)
    assert view["head"] == repo.head() and view["branch"] == repo.branch()
    assert view["dirty_paths"] == ["check.py", "new file.txt", "sdd/changes/demo/proposal.md"]
    assert view["untracked_paths"] == ["new file.txt"]
    assert view["ignored_paths"] == ["ignored.txt"]
    assert repo.changed_paths(base) == {".gitignore"}


def test_named_worktree_commit_keeps_main_head(project, tmp_path, implementation):
    repo = repository(project)
    main_head = repo.head()
    path = tmp_path / "isolated-task"
    repo.create_worktree(path, main_head, branch="sdd/test/task")
    task = repository(path)
    assert task.branch() == "sdd/test/task"
    assert repo.worktree(path) == dict(head=main_head, detached=False, branch="sdd/test/task")
    (path / "result.txt").write_bytes(b"committed candidate")
    stage(path, "result.txt")
    sha = commit(path, "Local candidate")
    assert task.head() != main_head and repo.head() == main_head
    assert not task.status()["dirty_paths"]
    assert task.changed_paths(main_head) == {"result.txt"}
    assert not (project / "result.txt").exists()


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
    assert file_mode(project, "check.py") == "100755"
    assert repo.content("", "foreign.txt") == b"staged"
    assert (project / "foreign.txt").read_bytes() == b"unstaged"
    assert repo.reverse_applicable(patch)
    with pytest.raises(Rejected):
        repo.remove_worktree(path)
    assert path.exists()
    stage(path, "check.py", "result.bin")
    commit(path, "Preserve task work before removal")
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
    before = (project / "merge.txt").read_bytes(), repo.index_patch()
    expected = repo.preview_patch(head, patch)
    assert ((project / "merge.txt").read_bytes(), repo.index_patch()) == before and repo.head() == head
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
