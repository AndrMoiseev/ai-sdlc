"""Git status carries source changes; file fingerprints belong to change docs."""
import pytest

from lib.common import Rejected, git
from lib.repository import repository


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


def test_status_parser_preserves_unusual_untracked_name(project, monkeypatch):
    from types import SimpleNamespace
    repo = repository(project)
    original = repo._run
    name = "100644 " + "0" * 40 + " 2\tlooks-tracked.txt"

    def listing(*args, **kwargs):
        if "status" in args:
            return SimpleNamespace(stdout=original(*args, **kwargs).stdout + ("? " + name + "\0").encode())
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "_run", listing)
    assert repo.status()["untracked_paths"] == [name]


pytestmark = pytest.mark.native_git
