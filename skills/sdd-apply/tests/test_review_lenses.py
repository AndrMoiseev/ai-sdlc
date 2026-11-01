"""Review coordination through the existing in-memory state/repository adapters."""
import pytest
import sys

from lib.review_policy import technical_debt


def start_code(driver):
    driver.role("code", "reviewer", lens_id="code")
    driver.send("review_start", {"role_id": "code"})


def result(driver, lens, **fields):
    return driver.send("review_result", {
        "role_id": "verifier" if lens == "verification" else "code",
        "verdict": "pass", "findings": [], "trace": "synthetic lens result",
        **({"test_integrity": "Required assertions inspected"} if lens == "verification" else {}),
        **fields})


@pytest.mark.parametrize("first", ["verification", "code"])
def test_both_lenses_share_one_round_and_complete_in_either_order(execution_checkpoint, first):
    driver = execution_checkpoint("executed")
    assert not driver.task.get("verification_results")
    start_code(driver)
    assert driver.task["review_rounds_started"] == 1
    assert set(driver.task["active_reviewers"]) == {"verification", "code"}
    driver.conclude()
    second = "code" if first == "verification" else "verification"
    assert result(driver, first)["pending_lenses"] == [second]
    assert driver.task["status"] == "reviewing"
    assert driver.task["review_rounds_completed"] == 0
    with pytest.raises(ValueError):
        driver.send("transfer")
    assert result(driver, second)["status"] == "integrating"
    assert driver.task["review_rounds_completed"] == 1


@pytest.mark.parametrize("fields", [
    {"test_integrity": "Code reviewer duplicated verification"},
    {"verdict": "more_checks"},
    {"findings": [{"severity": "blocker", "criteria": ["AC-one"], "path": "result.txt",
        "problem": "Missing acceptance behavior", "resolution": "Implement it"}]},
    {"findings": [{"severity": "blocker", "criteria": [], "path": "result.txt",
        "problem": "Missing acceptance behavior", "resolution": "Implement it",
        "proof": {"kind": "acceptance", "source": "spec.md#AC-one", "violation": "Missing"}}]},
])
def test_code_lens_cannot_take_verification_responsibilities(execution_checkpoint, fields):
    driver = execution_checkpoint("verified")
    start_code(driver)
    with pytest.raises(ValueError, match="Code review owns|belong to verification"):
        result(driver, "code", **fields)
    assert not driver.task["reviews"]


def test_verification_lens_cannot_take_architecture_responsibility(execution_checkpoint):
    driver = execution_checkpoint("verified")
    with pytest.raises(ValueError, match="architecture belongs to code"):
        result(driver, "verification", verdict="changes", findings=[{
            "severity": "blocker", "criteria": [], "path": "result.txt",
            "problem": "Wrong module boundary", "resolution": "Move dependency",
            "proof": {"kind": "architecture", "source": "design.md#DEC-one", "violation": "Reversed"}}])


def test_code_pass_cannot_override_unconfirmed_criterion(execution_checkpoint):
    driver = execution_checkpoint("executed")
    start_code(driver)
    driver.conclude(outcome="unavailable", check_request="Add the missing assertion")
    result(driver, "code")
    with pytest.raises(ValueError, match="Unconfirmed criteria"):
        result(driver, "verification")
    assert result(driver, "verification", verdict="more_checks")["status"] == "verifying"
    with pytest.raises(ValueError):
        driver.send("transfer")


def test_findings_from_both_lenses_have_distinct_journal_ids(execution_checkpoint):
    driver = execution_checkpoint("verified")
    start_code(driver)
    for lens in ("verification", "code"):
        result(driver, lens, findings=[{"severity": "recommendation", "criteria": [],
            "path": "result.txt", "problem": lens + " recommendation", "resolution": "Consider later"}])
    entries = technical_debt(driver.state)
    assert len({entry["finding_id"] for entry in entries}) == 2
    assert {entry["lens_id"] for entry in entries} == {"verification", "code"}


def test_static_check_failure_blocks_reviews_even_when_task_tests_pass(driver):
    driver.worktree()
    driver.send("checks_register", {"inventory": {"instructions": ["project rules"], "ci": ["lint"]},
        "additional": [{"id": "lint", "source": "project rules", "criteria": ["AC-one"],
            "run": {"command": [sys.executable, "-B", "-c",
                "from pathlib import Path; assert not Path('result.txt').exists()"]}}]})
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt"]})
    driver.run_checks("baseline")
    (driver.root / "result.txt").write_text("candidate")
    driver.freeze()
    run = driver.run_checks("independent")
    assert run["outcome"] == "failed"
    outputs = {item["check_id"]: item["outcome"] for item in driver.task["evidence"]}
    assert outputs["plan-1"] == "passed" and outputs["lint"] == "failed"
    for lens in ("verification", "code"):
        driver.role(lens, "reviewer", lens_id=lens)
        with pytest.raises(ValueError, match="failed, unavailable or stale"):
            driver.send("review_start", {"role_id": lens})
    assert driver.task["review_rounds_started"] == 0


@pytest.mark.parametrize("missing_lens", ["verification", "code"])
def test_finalization_requires_retained_results_from_both_lenses(execution_checkpoint, missing_lens):
    from lib.finalize import finalize
    driver = execution_checkpoint("accepted")
    state = driver.state
    task = state["tasks"]["TASK-one"]
    task["reviews"] = [review for review in task["reviews"] if review["lens_id"] != missing_lens]
    result = finalize(state, {}, driver.directory)
    assert result["result"] == "partial"
    assert any("Every required independent review lens" in gap["reason"] for gap in result["missing"])
