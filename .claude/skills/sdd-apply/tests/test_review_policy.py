from lib import artifact_storage as artifacts
from lib.state_storage import storage
import pytest

from lib.dashboard import render
from lib.review_policy import proven


def finding(proof=None, severity="blocker"):
    result = {"severity": severity, "criteria": [], "path": "result.txt",
              "problem": "Prefer another representation", "resolution": "Refactor representation"}
    if proof is not None:
        result["proof"] = proof
    return result


@pytest.fixture
def reviewing_driver(execution_checkpoint):
    return execution_checkpoint("reviewing")


def review(driver, findings, verdict="changes"):
    return driver.send("review_result", {
        "role_id": "reviewer", "candidate": driver.task["candidate"],
        "verdict": verdict, "findings": findings,
        "test_integrity": "Original assertions preserved", "trace": "synthetic-unit-test"})


@pytest.mark.parametrize("proof", [None, {}, "AC-one", {"kind": []},
    {"kind": "best_practice", "source": "style guide", "violation": "Less elegant"},
    {"kind": "acceptance", "source": "spec.md#AC-one", "violation": " "}])
def test_unsupported_proof_is_not_a_blocker(proof):
    assert not proven(finding(proof))


def test_unsupported_blocker_becomes_debt_without_repair(reviewing_driver):
    driver = reviewing_driver
    result = review(driver, [finding()])
    assert result["verdict"] == "pass"
    assert driver.task["status"] == "integrating"
    assert "failure" not in driver.task
    assert driver.task["test_repair_cycles_started"] == 0
    recorded = driver.task["reviews"][0]["findings"][0]
    assert recorded["severity"] == "recommendation"
    assert recorded["reported_severity"] == "blocker"
    driver.integrate()
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"


@pytest.mark.parametrize("kind", ["acceptance", "architecture", "project_rule"])
def test_each_contract_source_is_proven(kind):
    assert proven(finding({"kind": kind,
        "source": "approved-source.md#rule", "violation": "result.txt:1 contradicts the required format"}))


def test_proven_contract_violation_blocks_commit(reviewing_driver):
    driver = reviewing_driver
    result = review(driver, [finding({"kind": "acceptance",
        "source": "approved-source.md#rule", "violation": "result.txt:1 contradicts the required format"})])
    assert result["verdict"] == "changes"
    assert driver.task["failure"]["budget"] == "review"
    assert driver.task["reviews"][0]["findings"][0]["severity"] == "blocker"
    with pytest.raises(ValueError):
        driver.send("commit")


def test_proven_violation_cannot_hide_as_recommendation(reviewing_driver):
    driver = reviewing_driver
    with pytest.raises(ValueError, match="proven violations"):
        review(driver, [finding({"kind": "project_rule", "source": "AGENTS.md#format",
            "violation": "result.txt:1 has forbidden format"}, severity="recommendation")], verdict="pass")


def test_mixed_review_preserves_debt_and_blocks_on_proof(reviewing_driver):
    driver = reviewing_driver
    result = review(driver, [finding(), finding({"kind": "architecture",
        "source": "design.md#storage", "violation": "result.txt:1 contradicts the accepted storage format"})])
    assert result["verdict"] == "changes"
    assert [f["severity"] for f in driver.task["reviews"][0]["findings"]] == ["recommendation", "blocker"]
    render(driver.directory)
    journal = artifacts.read_text(driver.directory / "technical-debt.md")
    assert "Prefer another representation" in journal
    assert "## TASK-one/" in journal


def completed_with_debt(driver):
    review(driver, [finding()])
    driver.integrate()
    driver.send("commit")
    driver.send("accept")
    driver.role("final-context", "final_verifier")
    driver.send("check_run", {"role_id": "final-context", "stage": "final"})


def test_debt_survives_reload_and_does_not_prevent_completion(reviewing_driver):
    driver = reviewing_driver
    completed_with_debt(driver)
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "complete"
    assert driver.state["status"] == "completed"
    assert result["decisions"][0]["action"] == "defer"
    assert result["decisions"][0]["finding_id"] == result["recommendations"][0]["finding_id"]
    original = storage(driver.directory).read()
    render(driver.directory)
    journal = artifacts.read_bytes(driver.directory / "technical-debt.md")
    artifacts.write(driver.directory / "technical-debt.md", "damaged view")
    render(driver.directory)
    assert artifacts.read_bytes(driver.directory / "technical-debt.md") == journal
    assert storage(driver.directory).read() == original
    assert "[Journal](technical-debt.md)" in artifacts.read_text(driver.directory / "summary.md")


def test_finalization_cannot_automatically_fix_debt(reviewing_driver):
    driver = reviewing_driver
    from lib.review_policy import technical_debt
    completed_with_debt(driver)
    ident = technical_debt(driver.state)[0]["finding_id"]
    original = storage(driver.directory).read()
    with pytest.raises(ValueError, match="Fixes require explicit user approval"):
        driver.send("finalize", {"recommendation_decisions": [
            {"finding_id": ident, "action": "fix", "reason": "Easy cleanup"}]}, task_id=None)
    assert storage(driver.directory).read() == original
    assert driver.send("finalize", {}, task_id=None)["result"] == "complete"
