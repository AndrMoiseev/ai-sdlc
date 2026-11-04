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


def test_integration_conflict_stays_in_worktree_and_requires_new_checks_and_reviews(basis, tmp_path, project):
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
    original_head = repository(project).head()
    result = d.send("integrate")
    assert result["status"] == "conflict" and result["next"] == "worktree_refresh"
    assert not repository(project).dirty() and not repository(project).has_conflicts()
    assert (project / "result.txt").read_text() == "previous accepted task\n"
    with pytest.raises(ValueError):
        d.send("worktree_refresh", {"reason": "Integration conflict", "evidence": result})
    operation = f"event-{d.number}"
    from lib import artifact_storage as artifacts
    import json
    effect = d.directory / "runs" / d.state["run_id"] / "effects" / (operation + ".json")
    replacement = Path(json.loads(artifacts.read_text(effect))["request"]["precondition"]["new"])
    assert repository(replacement).has_conflicts()
    d.role("resolver", "executor")
    (replacement / "result.txt").write_text("previous accepted task\ntask content\n")
    stage(replacement, "result.txt")
    d.send("role_result", {"role_id": "resolver", "result": "Resolved both changes", "trace": "synthetic unit"})
    d.send("worktree_refresh_resolve", {"intent_id": operation, "role_id": "resolver", "resolution": "Retained both task contributions"})
    d.send("candidate")
    assert d.task["review_rounds_started"] == 1
    with pytest.raises(ValueError):
        d.send("transfer")
    assert repository(project).head() == original_head and not repository(project).dirty()
    d.verify("verification-after-conflict")
    d.review("code-after-conflict")
    assert d.task["review_rounds_started"] == 2
    d.integrate()
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
