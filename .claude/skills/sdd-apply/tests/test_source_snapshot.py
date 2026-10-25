"""A single Git listing retains tracked modes, deletions and untracked files."""
import pytest

from lib.common import Rejected, digest, git, source_snapshot


def test_snapshot_keeps_index_modes_deleted_and_explicitly_included_files(project):
    (project / "untracked file.txt").write_bytes(b"new")
    (project / "ignored.txt").write_bytes(b"owned")
    with (project / ".git/info/exclude").open("a") as stream:
        stream.write("\nignored.txt\n")
    (project / "check.py").chmod(0o755)
    git(project, "update-index", "--chmod=+x", "check.py")
    (project / "sdd/changes/demo/proposal.md").unlink()
    snapshot = source_snapshot(project, exclude=["sdd/changes/demo/review"], include=["ignored.txt"])
    files = snapshot["files"]
    assert files["check.py"]["git_mode"] == "100755"
    assert files["untracked file.txt"]["sha256"] == digest(b"new")
    assert files["ignored.txt"]["sha256"] == digest(b"owned")
    assert files["sdd/changes/demo/proposal.md"] is None
    assert not any(name.startswith("sdd/changes/demo/review/") for name in files)
    assert snapshot["digest"] == digest(files)


def test_snapshot_rejects_unmerged_index(project):
    # Create real index stages without needing a platform-dependent merge tool.
    blob = git(project, "rev-parse", "HEAD:check.py")
    import subprocess
    result = subprocess.run(["git", "-C", str(project), "update-index", "--index-info"],
                            input=f"0 {'0' * 40}\tcheck.py\n100644 {blob} 1\tcheck.py\n100644 {blob} 2\tcheck.py\n".encode(),
                            capture_output=True, shell=False)
    assert result.returncode == 0, result.stderr
    with pytest.raises(Rejected) as error:
        source_snapshot(project)
    assert error.value.code == "unmerged_index"


def test_untracked_filename_cannot_be_mistaken_for_index_metadata(tmp_path, monkeypatch):
    from lib import git_repository
    from types import SimpleNamespace
    # Feed a POSIX filename through the parser on every OS; Windows cannot
    # create tabs in names, so map just the filesystem lookup to a real file.
    name = "100644 " + "0" * 40 + " 2\tlooks-tracked.txt"
    path = tmp_path / "untracked.txt"
    path.write_bytes(b"untracked")
    calls = []
    def listing(root, *args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=("? " + name + "\0").encode())
    def contained(root, relative):
        assert relative == name
        return path
    monkeypatch.setattr(git_repository.GitRepository, "_run", listing)
    monkeypatch.setattr(git_repository, "contained", contained)
    assert source_snapshot(tmp_path)["files"][name]["sha256"] == digest(b"untracked")
    assert len(calls) == 1

pytestmark = pytest.mark.native_git
