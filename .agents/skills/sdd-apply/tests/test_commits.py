import pytest
from lib.common import git


def prepared(driver, project):
    driver.start()
    (project / "result.txt").write_text("verified result\n")
    driver.freeze()
    driver.verify()
    driver.review()


def test_only_owned_paths_with_foreign_index(driver, project):
    (project / "foreign.txt").write_text("staged\n")
    git(project, "add", "foreign.txt")
    (project / "foreign.txt").write_text("unstaged\n")
    staged = git(project, "show", ":foreign.txt", raw=True)
    prepared(driver, project)
    result = driver.send("commit")
    assert git(project, "diff-tree", "--no-commit-id", "--name-only", "-r", result["sha"]) == "result.txt"
    assert git(project, "show", ":foreign.txt", raw=True) == staged
    assert (project / "foreign.txt").read_text() == "unstaged\n"
    assert driver.send("accept")["status"] == "accepted"


def test_accept_without_commit_refused(driver, project):
    prepared(driver, project)
    with pytest.raises(ValueError, match="mandatory"):
        driver.send("accept")


def test_crash_after_git_before_state_recovers(driver, project, monkeypatch):
    prepared(driver, project)
    from lib import state
    real = state.write_json
    def fail(path, data):
        if path.name == "state.json":
            raise OSError("simulated crash")
        return real(path, data)
    monkeypatch.setattr(state, "write_json", fail)
    with pytest.raises(OSError, match="simulated"):
        driver.send("commit")
    head = git(project, "rev-parse", "HEAD")
    monkeypatch.setattr(state, "write_json", real)
    driver.number -= 1
    assert driver.send("commit")["sha"] == head
    assert driver.send("accept")["status"] == "accepted"


def test_hook_changes_candidate_rejected(driver, project):
    prepared(driver, project)
    hook = project / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook changed' >> result.txt\n", encoding="utf-8")
    hook.chmod(0o755)
    with pytest.raises(ValueError, match="changed"):
        driver.send("commit")
    assert driver.task["status"] == "committing"
    assert driver.task["commits"] == []
