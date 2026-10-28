"""Git status carries source changes; file fingerprints belong to change docs."""
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
    from types import SimpleNamespace
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
