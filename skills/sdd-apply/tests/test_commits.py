from lib.repository import repository
from repository_support import stage as stage_files, commit
import pytest
from pathlib import Path


def prepared(driver, project, integrate=True):
    driver.start()
    (driver.root / "result.txt").write_bytes(b"verified result\n")
    driver.freeze()
    driver.verify()
    driver.review()
    if integrate:
        driver.integrate()


def test_only_owned_paths_with_foreign_index(driver, project):
    (project / "foreign.txt").write_text("staged\n")
    stage_files(project, "foreign.txt")
    (project / "foreign.txt").write_text("unstaged\n")
    staged = repository(project).content("", "foreign.txt")
    prepared(driver, project, integrate=False)
    from lib.candidates import resolve
    candidate = resolve(driver.state, driver.task["candidate"])
    assert repository(driver.root).content(candidate["source"]["commit"], "result.txt") == b"verified result\n"
    driver.send("transfer")
    with pytest.raises(ValueError, match="clean|dirty|before verification"):
        driver.send("integrate")
    assert repository(project).content("", "foreign.txt") == staged
    assert (project / "foreign.txt").read_text() == "unstaged\n"
    assert not (project / "result.txt").exists()


def test_accept_without_commit_refused(execution_checkpoint):
    driver = execution_checkpoint("reviewed")
    with pytest.raises(ValueError, match="mandatory"):
        driver.send("accept")


def test_crash_after_git_before_state_recovers(execution_checkpoint, monkeypatch):
    driver = execution_checkpoint("reviewed")
    project = driver.state["basis"]["project_root"]
    from lib import state
    real = state.save
    def fail(path, data):
        raise OSError("simulated crash")
    monkeypatch.setattr(state, "save", fail)
    with pytest.raises(OSError, match="simulated"):
        driver.send("commit")
    head = repository(project).head()
    monkeypatch.setattr(state, "save", real)
    driver.number -= 1
    assert driver.send("commit")["sha"] == head
    assert driver.send("accept")["status"] == "accepted"


def test_hook_changes_candidate_rejected(execution_checkpoint, monkeypatch):
    driver = execution_checkpoint("started")
    project = driver.root
    (project / "result.txt").write_text("candidate before hook")
    repo = repository(project)
    original = repo.commit_tree
    def hook(tree, message):
        (project / "result.txt").write_text("hook changed")
        return original(tree, message)
    monkeypatch.setattr(repo, "commit_tree", hook)
    with pytest.raises(ValueError, match="changed|before verification"):
        driver.freeze()
    assert driver.task["status"] == "running"
    assert driver.task["commits"] == []
