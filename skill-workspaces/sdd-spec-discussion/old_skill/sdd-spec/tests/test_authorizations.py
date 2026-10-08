from lib.reviews import review_status
from lib.snapshots import snapshot
from test_review_records import project, report, write, finding


def user(tmp_path, kind, **extra):
    return dict(sdd_record="user", id="USER-" + kind.replace("_", "-"), kind=kind, scope={"stage": "document_review"}, response="Explicit instruction", date="2026-01-01T01:00:00Z", inputs=snapshot(tmp_path, "demo", "documents"), **extra)


def decisions(root, records):
    write(root / "review/decisions.md", {"schema_version": 1}, records)


def test_version_approval_vs_durable_work(tmp_path):
    root = project(tmp_path)
    approval = user(tmp_path, "document_approval")
    planning = user(tmp_path, "planning_command")
    planning["scope"]["work"] = "Plan this change"
    decisions(root, [approval, planning])
    (root / "design.md").write_text("expected edit")
    status = review_status(tmp_path, root, "documents")["approval_status"]
    assert not status["approved"]
    assert "USER-planning-command" in status["work_authorizations"]
    assert not status["ready"]


def test_historical_plan_without_tasks_does_not_block_documents(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, lens="plan", stage="plan")
    approval = user(tmp_path, "plan_approval")
    approval["scope"]["stage"] = "plan_review"
    approval["inputs"] = snapshot(tmp_path, "demo", "plan")
    decisions(root, [approval])
    (root / "tasks.md").unlink()
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert result["review_status"]["reports"]["run-one/plan"]["freshness"] == "stale"
    assert result["approval_status"]["applicability"]["USER-plan-approval"] is False
    assert not result["approval_status"]["approved"]


def test_related_findings_never_inherit_disposition(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding()])
    disposition = user(tmp_path, "finding_disposition", action="fix", completion=[])
    disposition["scope"]["findings"] = ["run-one/consistency/FIND-example"]
    decisions(root, [disposition])
    report(tmp_path, root, run="run-two", records=[finding()])
    write(root / "review/summary.md", {"schema_version": 1, "findings": [{"finding": "run-two/consistency/FIND-example", "related_to": ["run-one/consistency/FIND-example"], "duplicates": []}]})
    status = review_status(tmp_path, root, "documents")["review_status"]
    assert status["unresolved_findings"] == ["run-two/consistency/FIND-example"]
    assert status["unfinished_fixes"] == ["run-one/consistency/FIND-example"]
    disposition["completion"] = [{"finding": "run-one/consistency/FIND-example", "path": "design.md"}]
    decisions(root, [disposition])
    assert not review_status(tmp_path, root, "documents")["review_status"]["unfinished_fixes"]


def test_deferred_requires_return_and_cancelled_work_not_active(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding()])
    disposition = user(tmp_path, "finding_disposition", action="defer", reason="Later")
    disposition["scope"]["findings"] = ["run-one/consistency/FIND-example"]
    decisions(root, [disposition])
    assert review_status(tmp_path, root, "documents")["errors"]
    disposition.update(action="fix", status="cancelled")
    decisions(root, [disposition])
    status = review_status(tmp_path, root, "documents")
    assert not status["approval_status"]["work_authorizations"]
    assert status["review_status"]["unresolved_findings"]


def test_state_never_authorizes_and_broken_state_recovers(tmp_path):
    root = project(tmp_path)
    write(root / "state.md", {"schema_version": 1, "phase": "plan_approved", "approval_refs": ["USER-missing"]})
    result = review_status(tmp_path, root, "documents")
    assert not result["approval_status"]["approved"]
    assert result["warnings"][0]["code"] == "state_recovery"


def test_waiver_expiry_and_final_approval_does_not_waive(tmp_path):
    root = project(tmp_path)
    approval = user(tmp_path, "document_approval")
    decisions(root, [approval])
    assert not review_status(tmp_path, root, "documents")["approval_status"]["ready"]
    waiver = user(tmp_path, "review_waiver")
    waiver["scope"]["lenses"] = ["consistency"]
    decisions(root, [approval, waiver])
    assert review_status(tmp_path, root, "documents")["approval_status"]["ready"]
    (root / "design.md").write_text("new version")
    result = review_status(tmp_path, root, "documents")
    assert not result["approval_status"]["ready"]
    assert result["review_status"]["coverage"]["consistency"] == "missing"


def test_supersession_preserves_history_without_reactivating_old_work(tmp_path):
    root = project(tmp_path)
    original = user(tmp_path, "planning_command")
    original["scope"]["work"] = "Original scope"
    replacement = {**original, "id": "USER-replacement", "date": "2026-01-02T01:00:00Z", "supersedes": [original["id"]], "status": "cancelled"}
    decisions(root, [original, replacement])
    before = (root / "review/decisions.md").read_bytes()
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert not result["approval_status"]["work_authorizations"]
    assert (root / "review/decisions.md").read_bytes() == before
