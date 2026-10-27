from lib.reviews import review_status

from test_review_records import checkpoint, project, report, write, finding
import pytest
import yaml


def user(tmp_path, kind, **extra):
    return dict(sdd_record="user", work_kind="change", change_id="demo", id="USER-" + kind.replace("_", "-"), kind=kind, scope={"stage": "document_review"}, response="Explicit instruction", date="2026-01-01T01:00:00Z", basis_commit="a" * 40, **extra)


def decisions(root, records):
    write(root / "review/decisions.md", {"schema_version": 2, "work_kind": "change", "change_id": "demo"}, records)


def test_version_approval_vs_durable_work(tmp_path):
    root = project(tmp_path)
    approval = user(tmp_path, "document_approval")
    planning = user(tmp_path, "planning_command")
    planning["scope"]["work"] = "Plan this change"
    decisions(root, [approval, planning])
    (root / "design.md").write_text("expected edit")
    status = review_status(tmp_path, root, "documents")["approval_status"]
    assert status["approved"]
    assert "USER-planning-command" in status["work_authorizations"]
    assert status["ready"]


def test_historical_plan_without_tasks_does_not_block_documents(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root, lens="plan", stage="plan")
    approval = user(tmp_path, "plan_approval")
    approval["scope"]["stage"] = "plan_review"
    approval["basis_commit"] = "a" * 40
    decisions(root, [approval])
    (root / "tasks.md").unlink()
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert result["review_status"]["reports"]["run-one/plan"]["evidence"] == "current"
    assert result["approval_status"]["applicability"]["USER-plan-approval"] is True
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
    meta = checkpoint(root)
    meta.update(phase="plan_approved", approval_refs=["USER-missing"])
    (root / "state.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    result = review_status(tmp_path, root, "documents")
    assert not result["approval_status"]["approved"]
    assert result["warnings"][0]["code"] == "state_recovery"


@pytest.mark.parametrize("stage,kind,lens", [("documents", "document_approval", "consistency"), ("plan", "plan_approval", "plan")])
def test_durable_approval_and_review_remain_independent(tmp_path, stage, kind, lens):
    # Exercise real review and authorization parsing with an injected Git observation.
    root = project(tmp_path)
    approval = user(tmp_path, kind)
    approval["scope"]["stage"] = "document_review" if stage == "documents" else "plan_review"
    approval["basis_commit"] = "a" * 40
    decisions(root, [approval])
    result = review_status(tmp_path, root, stage)
    assert result["approval_status"]["ready"]
    assert result["review_status"]["coverage"][lens] == "missing"
    assert not result["review_status"]["complete"]
    report(tmp_path, root, lens=lens, stage=stage, result="incomplete")
    assert review_status(tmp_path, root, stage)["approval_status"]["ready"]
    report(tmp_path, root, lens=lens, stage=stage, records=[finding()])
    result = review_status(tmp_path, root, stage)
    assert result["approval_status"]["ready"]
    assert result["review_status"]["unresolved_findings"]
    disposition = user(tmp_path, "finding_disposition", action="fix", completion=[])
    disposition["scope"] = {"stage": approval["scope"]["stage"], "findings": [f"run-one/{lens}/FIND-example"]}
    disposition["basis_commit"] = approval["basis_commit"]
    decisions(root, [approval, disposition])
    result = review_status(tmp_path, root, stage)
    assert result["approval_status"]["ready"]
    assert result["review_status"]["unfinished_fixes"]
    waiver = user(tmp_path, "review_waiver")
    waiver["scope"] = {"stage": approval["scope"]["stage"], "lenses": [lens]}
    waiver["basis_commit"] = approval["basis_commit"]
    decisions(root, [approval, waiver])
    assert review_status(tmp_path, root, stage)["approval_status"]["ready"]
    (root / "design.md").write_text("new version")
    result = review_status(tmp_path, root, stage)
    assert result["approval_status"]["ready"]
    assert result["review_status"]["coverage"][lens] == "completed"
    approval["basis_commit"] = "a" * 40
    decisions(root, [approval])
    result = review_status(tmp_path, root, stage)
    assert result["approval_status"]["ready"]
    assert result["review_status"]["coverage"][lens] == "completed"
    approval["status"] = "cancelled"
    decisions(root, [approval])
    assert not review_status(tmp_path, root, stage)["approval_status"]["ready"]


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


def test_state_acceptance_does_not_approve_or_authorize_work(tmp_path):
    root = project(tmp_path)
    acceptance = user(tmp_path, "state_acceptance", message="Conversation message 12")
    acceptance.pop("basis_commit")
    acceptance.update(scope={}, accepted_commit="a" * 40)
    decisions(root, [acceptance])
    result = review_status(tmp_path, root, "plan")
    assert result["errors"] == []
    assert result["approval_status"]["approved"] is False
    assert result["approval_status"]["work_authorizations"] == {}


def test_approval_survives_accepted_commit_transition(tmp_path, checkpoint_observation):
    root = project(tmp_path)
    decisions(root, [user(tmp_path, "document_approval")])
    checkpoint_observation.update(head="b" * 40, accepted_commit="b" * 40)
    result = review_status(tmp_path, root, "documents")
    assert result["approval_status"]["approved"] is True
    assert result["approval_status"]["ready"] is True
