from lib.reviews import review_status, _validate_user, _reuse_decisions
from lib.documents import ValidationError

from test_review_records import checkpoint, project, report, write, finding
import pytest
import yaml


@pytest.mark.parametrize("declared", [{}, {"repeat": "original"}, {"last": "repeat", "repeat": "original"}])
def test_decision_reuse_chains_in_memory(declared):
    source = {"original": {"action": "defer"}}
    decisions_by_finding, origins = _reuse_decisions(source, declared)
    assert source == {"original": {"action": "defer"}}
    assert set(decisions_by_finding) == {"original", *declared}
    assert set(origins.values()) == {"original"}


def test_reuse_does_not_restore_missing_decisions_or_override_a_direct_choice():
    assert _reuse_decisions({}, {"repeat": "cancelled"}) == ({}, {})
    original = {"original": {"action": "reject"}}
    assert _reuse_decisions(original, {"repeat": "original"}, {"repeat"}) == (original, {"original": "original"})
    direct = {"original": {"action": "reject"}, "repeat": {"action": "fix"}}
    decisions_by_finding, origins = _reuse_decisions(direct, {"repeat": "original"})
    assert decisions_by_finding == direct
    assert origins["repeat"] == "repeat"
    with pytest.raises(ValidationError, match="Cyclic"):
        _reuse_decisions({}, {"first": "second", "second": "first"})


def user(tmp_path, kind, **extra):
    return dict(sdd_record="user", work_kind="change", change_id="demo", id="USER-" + kind.replace("_", "-"), kind=kind, scope={"stage": "review"}, response="Explicit instruction", date="2026-01-01T01:00:00Z", basis_commit="a" * 40, **extra)


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
    approval = user(tmp_path, "document_approval")
    approval["scope"]["stage"] = "review"
    approval["basis_commit"] = "a" * 40
    decisions(root, [approval])
    (root / "tasks.md").unlink()
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert result["review_status"]["reports"]["run-one/plan"]["evidence"] == "current"
    assert result["approval_status"]["applicability"]["USER-document-approval"] is True
    assert result["approval_status"]["approved"]
    assert not result["approval_status"]["ready"]
    assert "plan" not in result["review_status"]["required_lenses"]


def test_repeated_findings_reuse_only_explicitly_verified_decisions(tmp_path):
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
    write(root / "review/summary.md", {"schema_version": 1, "findings": [{
        "finding": "run-two/consistency/FIND-example", "related_to": [],
        "duplicates": ["run-one/consistency/FIND-example"],
        "decision_from": "run-one/consistency/FIND-example",
        "decision_basis": "Same issue, grounds and scope; the requested fix is still pending.",
    }]})
    status = review_status(tmp_path, root, "documents")["review_status"]
    assert not status["unresolved_findings"]
    assert status["reused_decisions"] == {"run-two/consistency/FIND-example": "run-one/consistency/FIND-example"}
    assert status["unfinished_fixes"] == ["run-one/consistency/FIND-example", "run-two/consistency/FIND-example"]
    disposition["completion"] = [{"finding": "run-one/consistency/FIND-example", "path": "design.md"}]
    decisions(root, [disposition])
    assert not review_status(tmp_path, root, "documents")["review_status"]["unfinished_fixes"]


@pytest.mark.parametrize("action", ["reject", "defer"])
def test_optional_recommendation_needs_no_reason_or_return_and_cancelled_work_not_active(tmp_path, action):
    root = project(tmp_path)
    report(tmp_path, root, records=[finding()])
    disposition = user(tmp_path, "finding_disposition", action=action)
    disposition["scope"]["findings"] = ["run-one/consistency/FIND-example"]
    decisions(root, [disposition])
    assert not review_status(tmp_path, root, "documents")["errors"]
    disposition.update(action="fix", status="cancelled")
    decisions(root, [disposition])
    status = review_status(tmp_path, root, "documents")
    assert not status["approval_status"]["work_authorizations"]
    assert status["review_status"]["unresolved_findings"]


def test_state_never_authorizes_and_broken_state_recovers(tmp_path):
    root = project(tmp_path)
    meta = checkpoint(root)
    meta.update(phase="approved", approval_refs=["USER-missing"])
    (root / "state.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    result = review_status(tmp_path, root, "documents")
    assert not result["approval_status"]["approved"]
    assert result["warnings"][0]["code"] == "state_recovery"


@pytest.mark.parametrize("stage,kind,lens", [("documents", "document_approval", "consistency"), ("documents", "document_approval", "premortem"), ("plan", "document_approval", "plan")])
def test_durable_approval_and_review_remain_independent(tmp_path, stage, kind, lens):
    # Exercise real review and authorization parsing with an injected Git observation.
    root = project(tmp_path)
    approval = user(tmp_path, kind)
    approval["scope"]["stage"] = "review" if stage == "documents" else "review"
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


@pytest.mark.parametrize("kind", ["review_consent", "review_waiver"])
@pytest.mark.parametrize("lenses,valid", [
    (["plan"], True), (["plan", "simplicity"], True), (["simplicity"], True),
    (["consistency"], True), (["premortem"], True), (["security"], True), (["simplicity", "simplicity"], False),
])
def test_plan_review_authorization_lenses_in_memory(kind, lenses, valid):
    from pathlib import Path
    record = user(None, kind)
    record["scope"] = {"stage": "review", "lenses": lenses}
    if kind == "review_consent":
        record["scope"]["run_id"] = "plan-run"
    if valid:
        _validate_user(record, Path("demo"), {}, oid_length=40)
    else:
        with pytest.raises(ValidationError):
            _validate_user(record, Path("demo"), {}, oid_length=40)
