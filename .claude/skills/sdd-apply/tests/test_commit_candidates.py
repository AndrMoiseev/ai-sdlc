"""Commit evidence replaces repository-wide source fingerprints."""
from pathlib import Path

import pytest

from lib.candidates import resolve
from lib.repository import repository
from lib.state import snapshot


def test_freeze_commits_only_in_task_worktree(driver, project):
    main_head = repository(project).head()
    driver.start()
    (driver.root / "result.txt").write_bytes(b"candidate")
    driver.freeze()
    source = resolve(driver.state, driver.task["candidate"])["source"]
    assert source["commit"] == repository(driver.root).head()
    assert source["commit"] != main_head
    assert not source["dirty_paths"]
    assert repository(project).head() == main_head
    assert not (project / "result.txt").exists()
    assert driver.task["status"] == "verifying" and driver.task["commits"] == []


@pytest.mark.native_git
def test_execution_snapshot_never_reads_external_file_content(driver, project, tmp_path, monkeypatch):
    root = tmp_path / "task-tree"
    repository(project).create_worktree(root, repository(project).head())
    change = root / "sdd/changes/demo"
    state = driver.state
    original = Path.read_bytes

    def inside_change_only(path):
        assert path.is_relative_to(change), f"Snapshot read external file {path}"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", inside_change_only)
    result = snapshot(state, root)
    assert result["files"]
    assert all(name.startswith("sdd/changes/demo/") for name in result["files"])
    assert result["commit"] == repository(root).head()


@pytest.mark.parametrize("mutation", ["tracked", "untracked", "head", "index-only"])
def test_each_git_mutation_invalidates_verified_candidate(execution_checkpoint, mutation):
    from repository_support import stage, commit
    driver = execution_checkpoint("verified")
    root = driver.root
    if mutation == "untracked":
        (root / "foreign.txt").write_text("new input")
    else:
        original = (root / "result.txt").read_bytes()
        (root / "result.txt").write_bytes(b"changed")
        if mutation in {"head", "index-only"}:
            stage(root, "result.txt")
        if mutation == "head":
            commit(root, "Different candidate")
        elif mutation == "index-only":
            (root / "result.txt").write_bytes(original)
    with pytest.raises(ValueError, match="changed|before verification"):
        driver.verify()


def test_candidate_commit_recovers_after_state_write_crash(execution_checkpoint, monkeypatch):
    from lib import state
    driver = execution_checkpoint("started")
    (driver.root / "result.txt").write_text("candidate")
    driver.send("role_result", {"role_id": "author", "result": "DONE", "trace": "unit-test"})
    with monkeypatch.context() as patch:
        def crash(*args):
            raise OSError("state write interrupted")
        patch.setattr(state, "save", crash)
        with pytest.raises(OSError, match="interrupted"):
            driver.send("candidate")
    sha = repository(driver.root).head()
    driver.number -= 1
    driver.send("candidate")
    assert resolve(driver.state, driver.task["candidate"])["source"]["commit"] == sha
    assert repository(driver.root).head() == sha


def test_legacy_file_snapshot_cannot_acquire_new_evidence(execution_checkpoint):
    from copy import deepcopy
    from lib.common import Rejected
    from lib.state import seal, save
    driver = execution_checkpoint("verified")
    state = driver.state
    legacy = deepcopy(resolve(state, driver.task["candidate"]))
    for field in ("commit", "branch", "dirty_paths"):
        legacy["source"].pop(field)
    state["tasks"]["TASK-one"]["candidate"] = legacy
    seal(state)
    save(driver.directory, state)
    with pytest.raises(Rejected) as error:
        driver.verify()
    assert error.value.code == "legacy_candidate"


def test_accepted_task_repair_returns_to_fresh_isolated_worktree(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    main = driver.root
    old = Path(driver.task["worktree"]["path"])
    head = repository(main).head()
    baseline = driver.task["baseline_checks"]
    driver.send("repair", {"reason": "Correct proven final defect", "defect_evidence": "Synthetic reproduction"})
    assert driver.task["worktree"] is None
    driver.worktree()
    assert driver.root != old and driver.root != main
    assert old.exists() and repository(driver.root).head() == head
    assert driver.task["baseline_checks"] == baseline
    (driver.root / "result.txt").write_text("repaired implementation")
    driver.freeze()
    assert repository(main).head() == head
    assert (main / "result.txt").read_text() == "verified result\n"


def test_no_change_repair_rechecks_same_tree_in_new_task_commit(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    main = driver.root
    head = repository(main).head()
    driver.send("budget_extend", {"budget": "review", "limit": 4,
                                  "source": "fixture-user", "text": "Authorize two repair reviews"})
    driver.send("repair", {"reason": "Recheck reported defect", "defect_evidence": "Synthetic report"})
    driver.worktree()
    driver.freeze()
    assert driver.verify("repair-verifier")["outcome"] == "passed"
    driver.review("repair-reviewer")
    driver.integrate(prefix="repair-")
    repaired = driver.send("commit")["sha"]
    assert repaired != head
    assert repository(main).tree(repaired) == repository(main).tree(head)
    assert driver.send("accept")["status"] == "accepted"
    assert repository(main).head() == repaired
