import pytest


def test_independent_run_catches_defect(driver, project):
    driver.start()
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


def test_stale_candidate_and_log_tampering(driver, project):
    driver.start()
    (project / "result.txt").write_text("ok")
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    log = driver.directory / driver.task["evidence"][-1]["log"]
    log.write_text("forged")
    driver.role("reviewer", "reviewer")
    with pytest.raises(ValueError):
        driver.send("review_start", {"role_id": "reviewer"})
    (project / "result.txt").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        driver.verify()


def test_author_cannot_verify_and_writer_must_stop(driver):
    driver.start()
    with pytest.raises(ValueError, match="finish"):
        driver.send("candidate")
    driver.freeze()
    with pytest.raises(ValueError, match="independent"):
        driver.send("check_run", {"role_id": "author", "stage": "independent"})


def test_additional_review_checks_invalidate_previous_pass(driver):
    driver.start()
    driver.freeze()
    driver.verify()
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


def test_timeout_is_unavailable_and_stops_own_process(tmp_path):
    import sys
    from lib.verification import run_command
    result = run_command(f'"{sys.executable}" -B -c "import time; time.sleep(30)"', tmp_path, .05)
    assert result["outcome"] == "unavailable"
    assert result["exit_code"] is None
    assert result["duration_seconds"] < 10


def test_initial_failing_check_blocks_plan(driver, project):
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    (project / "check.py").write_text("assert False\n")
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt"]})
    assert driver.send("check_run", {"role_id": "author", "stage": "baseline"})["outcome"] == "failed"
    assert driver.state["status"] == "blocked"
    assert driver.state["blockers"][0]["reason"] == "baseline_failed"
