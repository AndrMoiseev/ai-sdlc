"""Git status carries source changes; file fingerprints belong to change docs."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib.common import Rejected, git
from lib.repository import repository


@pytest.mark.native_git
def test_git_status_retains_modes_deleted_and_untracked_paths(project):
    (project / "untracked file.txt").write_bytes(b"new")
    (project / "ignored.txt").write_bytes(b"owned")
    with (project / ".git/info/exclude").open("a") as stream:
        stream.write("\nignored.txt\n")
    (project / "check.py").chmod(0o755)
    git(project, "update-index", "--chmod=+x", "check.py")
    (project / "sdd/changes/demo/proposal.md").unlink()
    state = repository(project).status(include_ignored=True)
    assert state["dirty_paths"] == ["check.py", "sdd/changes/demo/proposal.md", "untracked file.txt"]
    assert state["ignored_paths"] == ["ignored.txt"]


@pytest.mark.native_git
def test_inspect_rejects_unmerged_index(project):
    blob = git(project, "rev-parse", "HEAD:check.py")
    import subprocess
    result = subprocess.run(["git", "-C", str(project), "update-index", "--index-info"],
                            input=f"0 {'0' * 40}\tcheck.py\n100644 {blob} 1\tcheck.py\n100644 {blob} 2\tcheck.py\n".encode(),
                            capture_output=True, shell=False)
    assert result.returncode == 0, result.stderr
    with pytest.raises(Rejected) as error:
        repository(project).inspect()
    assert error.value.code == "unmerged_index"


def test_status_parser_preserves_unusual_untracked_name(tmp_path, monkeypatch):
    from lib.git_repository import GitRepository
    repo = GitRepository(tmp_path)
    name = "100644 " + "0" * 40 + " 2\tlooks-tracked.txt"

    def listing(*args, **kwargs):
        if "status" in args:
            return SimpleNamespace(stdout=("# branch.oid " + "1" * 40 + "\0# branch.head main\0? " + name + "\0").encode())
        assert args == ("ls-files", "-v", "--stage", "-z")
        return SimpleNamespace(stdout=b"")

    monkeypatch.setattr(repo, "_run", listing)
    assert repo.status()["untracked_paths"] == [name]


def test_indexed_symlink_uses_current_worktree(tmp_path, monkeypatch):
    from lib.git_repository import GitRepository
    from lib import common

    repo = GitRepository(tmp_path)
    name = "aliases/any name"
    link = repo.root / name
    indexed = f"H 120000 {'1' * 40} 0\t{name}\0".encode()
    status = b"# branch.oid abc\0# branch.head main\0"
    monkeypatch.setattr(repo, "_run", lambda *args: SimpleNamespace(
        stdout=indexed if args[0] == "ls-files" else status))
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link)

    def resolve_link(path, strict):
        assert path == link and strict
        if isinstance(target, Exception):
            raise target
        return target

    monkeypatch.setattr(common, "resolve", resolve_link)
    for target, code in [(repo.root, None), (repo.root.parent, "path_escape"),
                         (repo.root / ".git", "git_path"), (FileNotFoundError(), "invalid_symlink"),
                         (RuntimeError("symlink loop"), "invalid_symlink")]:
        if code is None:
            assert repo.status()["dirty_paths"] == []
        else:
            with pytest.raises(Rejected) as error:
                repo.status()
            assert error.value.code == code and str(link) in str(error.value)
    monkeypatch.setattr(Path, "is_symlink", lambda path: False)
    with pytest.raises(Rejected, match="not materialized"):
        repo.status()


@pytest.mark.native_git
def test_git_symlinks_in_document_snapshot(project, basis):
    # Only native Git and OS links expose checkout modes and directory traversal together.
    from lib.state import snapshot

    change = Path(basis["change_root"])
    alias = change / "alias"
    try:
        alias.symlink_to("design.md")
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows account cannot create symbolic links")
        raise
    (change / "parent").symlink_to("..", target_is_directory=True)
    names = [p.relative_to(project).as_posix() for p in (alias, change / "parent")]
    git(project, "config", "core.symlinks", "true")
    git(project, "add", "--", *names)
    git(project, "commit", "-qm", "Track internal symlinks")
    source = snapshot({"basis": basis})
    assert source["dirty_paths"] == []
    assert [source["files"][name] for name in names] == [{"symlink": "design.md"}, {"symlink": ".."}]
    assert not any(name.startswith(names[1] + "/") for name in source["files"])
    repo = repository(project)
    assert repo.tree_for_paths(names, repo.head()) == repo.tree(repo.head())
