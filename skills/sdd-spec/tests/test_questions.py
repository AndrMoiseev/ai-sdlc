"""Discussion records remain independent of document approval snapshots."""
import json

import pytest
import yaml

from lib.reviews import review_status
from lib.snapshots import snapshot
from test_authorizations import decisions, user
from test_check_command import create_project
from test_review_records import project, report, write


def split_checkpoint(root):
    """Reuse the discussion fixture to exercise the real legacy/new file boundary."""
    from lib.documents import read_document
    legacy = discussion_file(root, legacy=True, document_type="state")
    meta = read_document(legacy).meta
    meta.update(flow="draft", next_question=None,
                checks={"structure": "passed", "freshness": "current"})
    (root / "state.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    legacy.write_text("# Continuation\n\nKeep the user's remaining scope.\n", encoding="utf-8")
    return meta


def test_split_checkpoint_keeps_question_gate_and_normative_snapshot(tmp_path):
    # Real files are necessary here: the risk is selecting the wrong state file
    # and losing a blocker during migration. Reuse the existing discussion adapter.
    root = approved_bundle(tmp_path)
    before = snapshot(tmp_path, "demo", "documents")
    meta = split_checkpoint(root)
    assert review_status(tmp_path, root, "documents")["approval_status"]["ready"]
    discussion_file(root, [question()])
    meta["next_question"] = "Q-mode"
    (root / "state.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    result = review_status(tmp_path, root, "documents")
    assert not result["warnings"]
    assert result["discussion_status"]["blocking_questions"] == ["Q-mode"]
    assert not result["approval_status"]["ready"]
    assert snapshot(tmp_path, "demo", "documents") == before


@pytest.mark.parametrize("damage", ["yaml", "version", "frontmatter", "missing-prose", "question", "checks", "identity"])
def test_incomplete_split_checkpoint_cannot_admit_execution(tmp_path, damage):
    # The two-file selection/failure contract needs disk inputs; existing fixtures
    # provide approved evidence so this detects an accidental approval bypass.
    root = approved_bundle(tmp_path)
    meta = split_checkpoint(root)
    machine, prose = root / "state.yaml", root / "state.md"
    if damage == "yaml":
        machine.write_text("broken: [", encoding="utf-8")
    elif damage == "frontmatter":
        discussion_file(root, legacy=True)
    elif damage == "missing-prose":
        prose.unlink()
    else:
        if damage == "version":
            meta["schema_version"] = 99
        elif damage == "question":
            meta["next_question"] = "Q-missing"
        elif damage == "checks":
            meta["checks"]["structure"] = "invented"
        else:
            del meta["language"]
        machine.write_text(yaml.safe_dump(meta), encoding="utf-8")
    result = review_status(tmp_path, root, "documents")
    assert any(item["code"] == "state_recovery" for item in result["warnings"])
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]


def question(**extra):
    return dict(sdd_record="question", id="Q-mode", text="Which execution mode?",
                blocking=True, status="open", **extra)


def discussion_file(root, records=(), legacy=False, **metadata):
    meta = dict(schema_version=1, change_id=root.name, language="en")
    if legacy:
        meta.update(phase="drafting", awaiting="clarification",
                    updated_at="2026-01-01T00:00:00Z", document_links=[],
                    review_links=[], approval_refs=[])
    meta.update(metadata)
    path = root / ("state.md" if legacy else "questions.md")
    write(path, meta, records)
    return path


def approved_bundle(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root)
    decisions(root, [user(tmp_path, "document_approval")])
    return root


@pytest.mark.parametrize("legacy", [False, True])
def test_open_blocker_prevents_readiness_without_revoking_approval(tmp_path, legacy):
    root = approved_bundle(tmp_path)
    discussion_file(root, [question()], legacy)
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert result["approval_status"]["approved"]
    assert not result["approval_status"]["ready"]
    assert result["discussion_status"]["open_questions"] == ["Q-mode"]
    assert result["discussion_status"]["blocking_questions"] == ["Q-mode"]
    assert not result["discussion_status"]["complete"]


@pytest.mark.parametrize("legacy", [False, True])
def test_deferred_question_remains_open_without_blocking(tmp_path, legacy):
    root = approved_bundle(tmp_path)
    record = {**question(), "blocking": False, "reason": "Outside current scope", "return_at": "Before rollout"}
    discussion_file(root, [record], legacy)
    result = review_status(tmp_path, root, "documents")
    assert result["discussion_status"]["open_questions"] == ["Q-mode"]
    assert result["discussion_status"]["blocking_questions"] == []
    assert result["approval_status"]["ready"]
    del record["return_at"]
    discussion_file(root, [record], legacy)
    result = review_status(tmp_path, root, "documents")
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]
    assert result["warnings" if legacy else "errors"]


@pytest.mark.parametrize("legacy", [False, True])
def test_resolved_question_evidence_and_legacy_compatibility(tmp_path, legacy):
    root = approved_bundle(tmp_path)
    record = {**question(), "status": "resolved"}
    discussion_file(root, [record], legacy)
    result = review_status(tmp_path, root, "documents")
    assert result["discussion_status"]["complete"] is legacy
    assert result["approval_status"]["ready"] is legacy
    (root / "decisions.md").write_text("# Decisions\n\n### Mode\nUser chose serial.\n", encoding="utf-8")
    record["resolution"] = "decisions.md#mode"
    discussion_file(root, [record], legacy)
    result = review_status(tmp_path, root, "documents")
    assert result["approval_status"]["ready"]
    assert result["discussion_status"]["open_questions"] == []
    assert "authorship" in result["discussion_status"]["provenance"]
    assert "semantic completeness" in result["discussion_status"]["provenance"]


@pytest.mark.parametrize("reference", ["missing.md#mode", "../outside.md#mode", "C:/outside.md#mode", "https://example.com", "design.md#", "#mode", "review", "", 3, "design.md\0"])
def test_invalid_resolution_references_block_readiness(tmp_path, reference):
    root = approved_bundle(tmp_path)
    discussion_file(root, [{**question(), "status": "resolved", "resolution": reference}])
    result = review_status(tmp_path, root, "documents")
    assert result["errors"][0]["code"] == "questions_structure"
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]


def test_duplicate_across_files_cannot_shadow_unresolved_question(tmp_path):
    root = approved_bundle(tmp_path)
    discussion_file(root, [{**question(), "status": "resolved", "resolution": "design.md"}])
    discussion_file(root, [question()], legacy=True)
    result = review_status(tmp_path, root, "documents")
    assert any(e["code"] == "duplicate_question" for e in result["errors"])
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]


@pytest.mark.parametrize("metadata", [{"change_id": "other"}, {"document_type": "state"}, {"schema_version": 99}, {"language": ""}, {"unexpected": True}])
def test_question_metadata_is_strict(tmp_path, metadata):
    root = approved_bundle(tmp_path)
    discussion_file(root, **metadata)
    result = review_status(tmp_path, root, "documents")
    assert result["errors"]
    assert not result["approval_status"]["ready"]


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("content", [b"\xff", b"---\nbroken: [\n---\n", b"No frontmatter\n"])
def test_corrupt_discussion_is_not_complete(tmp_path, legacy, content):
    root = approved_bundle(tmp_path)
    path = discussion_file(root, legacy=legacy)
    path.write_bytes(content)
    result = review_status(tmp_path, root, "documents")
    assert result["warnings" if legacy else "errors"]
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]


def test_missing_legacy_checkpoint_preserves_existing_approval(tmp_path):
    root = approved_bundle(tmp_path)
    result = review_status(tmp_path, root, "documents")
    assert result["warnings"][0]["code"] == "state_recovery"
    assert result["approval_status"]["ready"]
    assert "available question records only" in result["discussion_status"]["provenance"]


def test_discussion_files_do_not_change_review_snapshots(tmp_path):
    root = approved_bundle(tmp_path)
    before = {stage: snapshot(tmp_path, "demo", stage) for stage in ("documents", "plan")}
    discussion_file(root, [question()])
    discussion_file(root, legacy=True)
    (root / "decisions.md").write_text("### Mode\nProposed by agent; awaiting user.\n", encoding="utf-8")
    assert before == {stage: snapshot(tmp_path, "demo", stage) for stage in before}
    result = review_status(tmp_path, root, "documents")
    assert result["approval_status"]["approved"]
    assert result["review_status"]["complete"]
    assert not result["approval_status"]["ready"]


@pytest.mark.parametrize("mode,exit_code", [("open", 0), ("invalid", 1), ("corrupt", 1), ("nul-resolution", 1)])
def test_command_reports_discussion_separately(tmp_path, mode, exit_code, command_main):
    root = create_project(tmp_path)
    path = discussion_file(root, [question()])
    if mode == "invalid":
        discussion_file(root, [question()], change_id="other")
    elif mode == "corrupt":
        path.write_bytes(b"\xff")
    elif mode == "nul-resolution":
        discussion_file(root, [{**question(), "status": "resolved", "resolution": "design.md\0"}])
    result = command_main(tmp_path)
    assert result.returncode == exit_code, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["discussion_status"]["complete"] is False
    assert output["approval_status"]["ready"] is False
    if mode == "open":
        assert output["discussion_status"]["blocking_questions"] == ["Q-mode"]
    elif mode == "nul-resolution":
        assert output["errors"][0]["code"] == "questions_structure"
        assert "NUL" in output["errors"][0]["message"]
