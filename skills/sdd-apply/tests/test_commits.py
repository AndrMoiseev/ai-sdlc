from lib.repository import repository
from repository_support import stage as stage_files, commit
import pytest
from pathlib import Path


def prepared(driver, project):
    driver.start()
    (project / "result.txt").write_text("verified result\n")
    driver.freeze()
    driver.verify()
    driver.review()


def test_only_owned_paths_with_foreign_index(driver, project):
    (project / "foreign.txt").write_text("staged\n")
    stage_files(project, "foreign.txt")
    (project / "foreign.txt").write_text("unstaged\n")
    staged = repository(project).content("", "foreign.txt")
    prepared(driver, project)
    result = driver.send("commit")
    assert repository(project).content(result["sha"], "result.txt") == (project / "result.txt").read_bytes()
    assert repository(project).tracked(result["sha"]) - repository(project).tracked(result["parent"]) == {"result.txt"}
    assert repository(project).content("", "foreign.txt") == staged
    assert (project / "foreign.txt").read_text() == "unstaged\n"
    assert driver.send("accept")["status"] == "accepted"


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
    driver = execution_checkpoint("reviewed")
    project = Path(driver.state["basis"]["project_root"])
    repo = repository(project)
    original = repo.commit_tree
    def hook(tree, message):
        (project / "result.txt").write_text("hook changed")
        return original(tree, message)
    monkeypatch.setattr(repo, "commit_tree", hook)
    with pytest.raises(ValueError, match="changed"):
        driver.send("commit")
    assert driver.task["status"] == "committing"
    assert driver.task["commits"] == []
