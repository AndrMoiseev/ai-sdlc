from pathlib import Path
from conftest import Driver
from lib import artifact_storage as artifacts
from lib.repository import repository
from repository_support import stage, commit, set_mode, file_mode
import pytest


def test_binary_untracked_transfer_retains_worktree_verification(basis, tmp_path, project):
    d = Driver(basis)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    (Path(wt["path"]) / "result.txt").write_bytes(b"\x00\xffbinary\n")
    d.freeze()
    d.verify()
    assert d.review()["status"] == "integrating"
    package = d.send("transfer")
    assert artifacts.read_bytes(d.directory / package["path"])
    d.send("integrate")
    assert (project / "result.txt").read_bytes() == b"\x00\xffbinary\n"
    assert "candidate" not in d.task
    (project / "result.txt").write_bytes(b"unrecorded edit\n")
    with pytest.raises(ValueError, match="changed after transfer"):
        d.send("candidate")
    (project / "result.txt").write_bytes(b"\x00\xffbinary\n")
    d.send("candidate")
    assert d.task["status"] == "committing"
    assert d.task["review_rounds_started"] == d.task["review_rounds_completed"] == 1
    d.send("commit")
    assert d.send("accept")["status"] == "accepted"
    assert repository(project).content("HEAD", "result.txt") == b"\x00\xffbinary\n"


def test_conflict_resolution_records_transfer_without_repeating_checks(basis, tmp_path, project):
    d = Driver(basis)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    (Path(wt["path"]) / "result.txt").write_text("task content\n")
    d.freeze()
    d.verify()
    d.review()
    d.send("transfer")
    (project / "result.txt").write_text("previous accepted task\n")
    stage(project, "result.txt")
    commit(project, "fixture concurrent accepted task")
    from repository_support import accept_execution_source
    accept_execution_source(d)
    with pytest.raises(ValueError):
        d.send("integrate")
    operation = f"event-{d.number}"
    assert repository(project).has_conflicts()
    d.role("resolver", "executor")
    (project / "result.txt").write_text("previous accepted task\ntask content\n")
    stage(project, "result.txt")
    d.send("role_result", {"role_id": "resolver", "result": "Resolved both changes", "trace": "synthetic unit"})
    d.send("integration_resolve", {"intent_id": operation, "role_id": "resolver", "resolution": "Retained both task contributions"})
    d.send("candidate")
    assert d.task["review_rounds_started"] == 1
    d.send("commit")
    assert d.send("accept")["status"] == "accepted"


def test_staged_executable_mode_is_in_transfer(basis, tmp_path):
    d = Driver(basis)
    wt = d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    d.start()
    path = Path(wt["path"]) / "check.py"
    path.chmod(0o755)
    set_mode(wt["path"], "check.py", True)
    (Path(wt["path"]) / "result.txt").write_text("ok\n")
    d.freeze()
    d.verify()
    d.review()
    package = d.send("transfer")
    assert artifacts.read_bytes(d.directory / package["path"])
    d.send("integrate")
    assert file_mode(basis["project_root"], "check.py") == "100755"


@pytest.mark.parametrize("damage", ["main-files", "main-head", "worktree", "evidence"])
def test_transfer_integrity_still_gates_acceptance(execution_checkpoint, damage):
    # Rule matrix uses existing memory adapters; real Git contracts cover transfer.
    from repository_support import write_file
    d = execution_checkpoint("reviewed", memory_worktree=True)
    root = Path(d.state["basis"]["project_root"])
    if damage in {"main-files", "main-head"}:
        write_file(root, "result.txt", b"unverified edit\n")
        if damage == "main-head":
            stage(root, "result.txt")
            commit(root, "unexpected main commit")
    elif damage == "worktree":
        write_file(Path(d.task["worktree"]["path"]), "result.txt", b"changed source\n")
    else:
        artifacts.write(d.directory / d.task["evidence"][-1]["log"], b"corrupt evidence")
    with pytest.raises(ValueError):
        d.send("commit")
    assert d.task["status"] != "accepted"
