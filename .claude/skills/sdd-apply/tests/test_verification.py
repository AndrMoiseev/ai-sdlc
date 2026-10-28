from lib import artifact_storage as artifacts
import pytest
from pathlib import Path


@pytest.mark.parametrize("target", ["result.txt", "sdd/changes/demo/design.md"])
def test_successful_command_cannot_hide_changes_during_verification(execution_checkpoint, target):
    import json
    from lib.candidates import resolve
    driver = execution_checkpoint("started")
    (driver.root / "check.py").write_text(
        "from pathlib import Path\n" + f"Path({target!r}).write_text('changed by check')\n")
    driver.freeze()
    before = resolve(driver.state, driver.task["candidate"])["source"]
    result = driver.verify()
    assert result["outcome"] == "failed"
    log = json.loads(artifacts.read_text(driver.directory / result["log"]))
    assert log["outputs"][0]["exit_code"] == 0
    assert log["before"] == before and log["after"] != before
    assert driver.task["evidence"][-1]["outcome"] == "stale"


def test_independent_run_catches_defect(execution_checkpoint):
    driver = execution_checkpoint("started")
    project = driver.root
    (project / "check.py").write_text("assert False, 'real defect'\n")
    driver.freeze()
    assert driver.verify()["outcome"] == "failed"
    assert driver.task["last_check_failed"]
    assert driver.task["test_repair_cycles_started"] == 0
    with pytest.raises(ValueError, match="reserve"):
        driver.verify()
    driver.role("reviewer", "reviewer")
    with pytest.raises(ValueError, match="required check"):
        driver.send("review_start", {"role_id": "reviewer"})


def test_stale_candidate_and_log_tampering(execution_checkpoint):
    driver = execution_checkpoint("verified")
    project = driver.root
    log = driver.directory / driver.task["evidence"][-1]["log"]
    artifacts.write(log, "forged")
    driver.role("reviewer", "reviewer")
    with pytest.raises(ValueError):
        driver.send("review_start", {"role_id": "reviewer"})
    (project / "result.txt").write_text("changed")
    with pytest.raises(ValueError, match="changed|before verification"):
        driver.verify()


def test_author_cannot_verify_and_writer_must_stop(execution_checkpoint):
    driver = execution_checkpoint("started")
    with pytest.raises(ValueError, match="finish"):
        driver.send("candidate")
    driver.freeze()
    with pytest.raises(ValueError, match="independent"):
        driver.send("check_run", {"role_id": "author", "stage": "independent"})


def test_additional_review_checks_invalidate_previous_pass(execution_checkpoint):
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    old = driver.task["candidate"]
    command = driver.task["checks"][0]["run"]["command"]
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [{"id": "extra", "source": "review", "criteria": ["AC-one"], "run": {"command": command}}]})
    assert driver.task["candidate"] != old
    driver.role("new-reviewer", "reviewer")
    with pytest.raises(ValueError, match="Every required"):
        driver.send("review_start", {"role_id": "new-reviewer"})
    assert driver.verify()["outcome"] == "passed"
    assert driver.send("review_start", {"role_id": "new-reviewer"})["round"] == 2


@pytest.mark.native_process
def test_timeout_is_unavailable_and_stops_own_process(tmp_path):
    import sys
    from lib.verification import run_command
    result = run_command([sys.executable, "-B", "-c", "import time; time.sleep(30)"], tmp_path, .05)
    assert result["outcome"] == "unavailable"
    assert result["exit_code"] is None
    assert result["duration_seconds"] < 10


def test_initial_failing_check_blocks_plan(driver, project):
    from repository_support import stage, commit
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    (project / "check.py").write_text("assert False\n")
    stage(project, "check.py")
    commit(project, "Existing failing check")
    from repository_support import accept_execution_source
    accept_execution_source(driver)
    driver.worktree()
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt"]})
    assert driver.send("check_run", {"role_id": "author", "stage": "baseline"})["outcome"] == "failed"
    assert driver.state["status"] == "blocked"
    assert driver.state["blockers"][0]["reason"] == "baseline_failed"


@pytest.mark.native_process
def test_arguments_are_literal_and_paths_with_spaces_work(tmp_path):
    import json
    import sys
    from lib.verification import run_command
    cwd = tmp_path / "working directory"
    cwd.mkdir()
    script = cwd / "echo arguments.py"
    script.write_text("import json, sys; print(json.dumps(sys.argv[1:]))\n")
    arguments = ["", "two words", 'a"quote', "trailing\\", "&&", ";", "|", ">", "*.py", "$HOME", "%TEMP%", "$(echo unexpected)"]
    command = [sys.executable, "-B", str(script), *arguments]
    result = run_command(command, cwd, 10)
    assert result["outcome"] == "passed", result
    assert json.loads(result["stdout"]) == arguments
    assert result["command"] == command
    assert list(cwd.iterdir()) == [script]


@pytest.mark.parametrize("command", ["echo unsafe > marker", [], [""], [None], ["runner", "bad\0arg"]])
@pytest.mark.native_process
def test_invalid_or_legacy_command_never_starts_process(tmp_path, monkeypatch, command):
    from lib import verification
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid command reached subprocess")
    monkeypatch.setattr(verification.subprocess, "Popen", unexpected)
    result = verification.run_command(command, tmp_path, 10)
    assert result["outcome"] == "unavailable"
    assert result["limitation"] == "command_format"
    assert result["exit_code"] is None


@pytest.mark.native_process
def test_nonzero_exit_and_missing_executable(tmp_path):
    import sys
    from lib.verification import run_command
    result = run_command([sys.executable, "-B", "-c", "import sys; sys.stderr.write('failure'); sys.exit(7)"], tmp_path, 10)
    assert result["outcome"] == "failed"
    assert result["exit_code"] == 7
    assert result["stderr"].endswith("failure")
    result = run_command([str(tmp_path / "missing-executable")], tmp_path, 10)
    assert result["outcome"] == "unavailable"
    assert result["exit_code"] is None


@pytest.mark.native_process
def test_explicit_shell_script(tmp_path):
    import os
    import shutil
    from lib.verification import run_command
    if os.name == "nt":
        script = tmp_path / "verify.cmd"
        script.write_text("@echo off\necho explicit-shell\nexit /b 7\n")
        command = [os.environ["COMSPEC"], "/d", "/c", script.name]
    else:
        script = tmp_path / "verify.sh"
        script.write_text("echo explicit-shell\nexit 7\n")
        command = [shutil.which("sh"), str(script)]
    result = run_command(command, tmp_path, 10)
    assert result["stdout"].strip() == "explicit-shell"
    assert result["exit_code"] == 7
    assert result["outcome"] == "failed"


def test_additional_check_rejects_string_command(driver):
    with pytest.raises(ValueError, match="argument array"):
        driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [{"id": "extra", "source": "ci", "run": {"command": "pytest"}}]})
    assert not driver.task["checks"]


def test_extension_rejects_string_command(execution_checkpoint):
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    with pytest.raises(ValueError, match="argument array"):
        driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [{"id": "extra", "source": "review", "criteria": ["AC-one"], "run": {"command": "pytest"}}]})
    assert len(driver.task["checks"]) == 1
