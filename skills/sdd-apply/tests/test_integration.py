from pathlib import Path
from conftest import Driver
from lib.common import git
import pytest


def test_binary_untracked_transfer_requires_new_verification(basis, tmp_path, project):
    d = Driver(basis, parallel=True)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    (Path(wt["path"]) / "result.txt").write_bytes(b"\x00\xffbinary\n")
    d.freeze()
    d.verify()
    assert d.review()["status"] == "integrating"
    package = d.send("transfer")
    assert "GIT binary patch" in (d.directory / package["path"]).read_text()
    d.send("integrate")
    assert (project / "result.txt").read_bytes() == b"\x00\xffbinary\n"
    assert d.task["candidate"] is None
    d.send("candidate")
    d.role("integration-verifier", "verifier")
    assert d.send("check_run", {"role_id": "integration-verifier", "stage": "integration"})["outcome"] == "passed"
    assert d.review("integration-reviewer")["status"] == "committing"
    d.send("commit")
    assert d.send("accept")["status"] == "accepted"
    assert git(project, "show", "HEAD:result.txt", raw=True) == b"\x00\xffbinary\n"


def test_conflict_resolution_requires_new_main_branch_evidence(basis, tmp_path, project):
    d = Driver(basis, parallel=True)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    (Path(wt["path"]) / "result.txt").write_text("task content\n")
    d.freeze()
    d.verify()
    d.review()
    d.send("transfer")
    (project / "result.txt").write_text("previous accepted task\n")
    git(project, "add", "result.txt")
    git(project, "commit", "-m", "fixture concurrent accepted task")
    with pytest.raises(ValueError):
        d.send("integrate")
    operation = f"event-{d.number}"
    assert git(project, "ls-files", "--unmerged")
    d.role("resolver", "executor")
    (project / "result.txt").write_text("previous accepted task\ntask content\n")
    git(project, "add", "result.txt")
    d.send("role_result", {"role_id": "resolver", "result": "Resolved both changes", "trace": "synthetic unit"})
    d.send("integration_resolve", {"intent_id": operation, "role_id": "resolver", "resolution": "Retained both task contributions"})
    d.send("candidate")
    d.role("integration-verifier", "verifier")
    assert d.send("check_run", {"role_id": "integration-verifier", "stage": "integration"})["outcome"] == "passed"
    d.review("integration-reviewer")
    d.send("commit")
    assert d.send("accept")["status"] == "accepted"


def test_staged_executable_mode_is_in_transfer(basis, tmp_path):
    d = Driver(basis, parallel=True)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    path = Path(wt["path"]) / "check.py"
    path.chmod(0o755)
    git(wt["path"], "update-index", "--chmod=+x", "check.py")
    (Path(wt["path"]) / "result.txt").write_text("ok\n")
    d.freeze()
    d.verify()
    d.review()
    package = d.send("transfer")
    assert "new mode 100755" in (d.directory / package["path"]).read_text()
