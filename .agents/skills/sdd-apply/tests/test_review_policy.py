import pytest

from lib.dashboard import render


def finding(proof=None, severity="blocker"):
    result = {"severity": severity, "criteria": [], "path": "result.txt",
              "problem": "Prefer another representation", "resolution": "Refactor representation"}
    if proof is not None:
        result["proof"] = proof
    return result


def review(driver, project, findings, verdict="changes"):
    driver.start()
    (project / "result.txt").write_text("verified result\n")
    driver.freeze()
    driver.verify()
    driver.role("reviewer", "reviewer")
    driver.send("review_start", {"role_id": "reviewer"})
    return driver.send("review_result", {
        "role_id": "reviewer", "candidate": driver.task["candidate"],
        "verdict": verdict, "findings": findings,
        "test_integrity": "Original assertions preserved", "trace": "synthetic-unit-test"})


@pytest.mark.parametrize("proof", [None, {}, "AC-one", {"kind": []},
    {"kind": "best_practice", "source": "style guide", "violation": "Less elegant"},
    {"kind": "acceptance", "source": "spec.md#AC-one", "violation": " "}])
def test_unsupported_blocker_becomes_debt_without_repair(driver, project, proof):
    result = review(driver, project, [finding(proof)])
    assert result["verdict"] == "pass"
    assert driver.task["status"] == "committing"
    assert "failure" not in driver.task
    assert driver.task["test_repair_cycles_started"] == 0
    recorded = driver.task["reviews"][0]["findings"][0]
    assert recorded["severity"] == "recommendation"
    assert recorded["reported_severity"] == "blocker"
    driver.send("commit")
    assert driver.send("accept")["status"] == "accepted"


@pytest.mark.parametrize("kind", ["acceptance", "architecture", "project_rule"])
def test_each_contract_source_can_block(driver, project, kind):
    result = review(driver, project, [finding({"kind": kind,
        "source": "approved-source.md#rule", "violation": "result.txt:1 contradicts the required format"})])
    assert result["verdict"] == "changes"
    assert driver.task["failure"]["budget"] == "review"
    assert driver.task["reviews"][0]["findings"][0]["severity"] == "blocker"
    with pytest.raises(ValueError):
        driver.send("commit")


def test_proven_violation_cannot_hide_as_recommendation(driver, project):
    with pytest.raises(ValueError, match="proven violations"):
        review(driver, project, [finding({"kind": "project_rule", "source": "AGENTS.md#format",
            "violation": "result.txt:1 has forbidden format"}, severity="recommendation")], verdict="pass")


def test_mixed_review_preserves_debt_and_blocks_on_proof(driver, project):
    result = review(driver, project, [finding(), finding({"kind": "architecture",
        "source": "design.md#storage", "violation": "result.txt:1 contradicts the accepted storage format"})])
    assert result["verdict"] == "changes"
    assert [f["severity"] for f in driver.task["reviews"][0]["findings"]] == ["recommendation", "blocker"]
    render(driver.directory)
    journal = (driver.directory / "technical-debt.md").read_text(encoding="utf-8")
    assert "Prefer another representation" in journal
    assert "## TASK-one/" in journal


def completed_with_debt(driver, project):
    review(driver, project, [finding()])
    driver.send("commit")
    driver.send("accept")
    driver.role("final-context", "final_verifier")
    driver.send("check_run", {"role_id": "final-context", "stage": "final"})


def test_debt_survives_reload_and_does_not_prevent_completion(driver, project):
    completed_with_debt(driver, project)
    result = driver.send("finalize", {}, task_id=None)
    assert result["result"] == "complete"
    assert driver.state["status"] == "completed"
    assert result["decisions"][0]["action"] == "defer"
    assert result["decisions"][0]["finding_id"] == result["recommendations"][0]["finding_id"]
    original = (driver.directory / "state.json").read_bytes()
    render(driver.directory)
    journal = (driver.directory / "technical-debt.md").read_bytes()
    (driver.directory / "technical-debt.md").write_text("damaged view")
    render(driver.directory)
    assert (driver.directory / "technical-debt.md").read_bytes() == journal
    assert (driver.directory / "state.json").read_bytes() == original
    assert "[Journal](technical-debt.md)" in (driver.directory / "summary.md").read_text(encoding="utf-8")


def test_finalization_cannot_automatically_fix_debt(driver, project):
    from lib.review_policy import technical_debt
    completed_with_debt(driver, project)
    ident = technical_debt(driver.state)[0]["finding_id"]
    original = (driver.directory / "state.json").read_bytes()
    with pytest.raises(ValueError, match="Fixes require explicit user approval"):
        driver.send("finalize", {"recommendation_decisions": [
            {"finding_id": ident, "action": "fix", "reason": "Easy cleanup"}]}, task_id=None)
    assert (driver.directory / "state.json").read_bytes() == original
    assert driver.send("finalize", {}, task_id=None)["result"] == "complete"
