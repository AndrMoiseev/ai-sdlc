"""Discussion records remain independent of document approval snapshots."""
import json

import pytest
import yaml

from lib.reviews import review_status

from test_authorizations import decisions, user
from test_check_command import create_project
from test_review_records import checkpoint, project, report, write


def test_checkpoint_keeps_question_gate_and_normative_snapshot(tmp_path):
    # Real files are necessary here: the risk is selecting the wrong state file
    # and admitting an incomplete checkpoint. Reuse the existing discussion adapter.
    root = approved_bundle(tmp_path)
    before = (root / "design.md").read_bytes()
    meta = checkpoint(root)
    assert review_status(tmp_path, root, "documents")["approval_status"]["ready"]
    discussion_file(root, [question()])
    meta["next_question"] = "Q-mode"
    (root / "state.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    result = review_status(tmp_path, root, "documents")
    assert not result["warnings"]
    assert result["discussion_status"]["blocking_questions"] == ["Q-mode"]
    assert not result["approval_status"]["ready"]
    assert (root / "design.md").read_bytes() == before


@pytest.mark.parametrize("damage", ["yaml", "version", "frontmatter", "missing-prose", "missing-yaml", "question", "checks", "identity", "flow", "next_question", "missing-checks", "state-question"])
def test_incomplete_checkpoint_cannot_admit_execution(tmp_path, damage):
    # The two-file selection/failure contract needs disk inputs; existing fixtures
    # provide approved evidence so this detects an accidental approval bypass.
    root = approved_bundle(tmp_path)
    meta = checkpoint(root)
    machine, prose = root / "state.yaml", root / "state.md"
    if damage == "yaml":
        machine.write_text("broken: [", encoding="utf-8")
    elif damage == "frontmatter":
        write(prose, meta)
    elif damage == "missing-yaml":
        machine.unlink()
    elif damage == "state-question":
        prose.write_text("# Continuation\n\n### Question\n\n```yaml\n" + yaml.safe_dump(question()) + "```\n", encoding="utf-8")
    elif damage == "missing-prose":
        prose.unlink()
    else:
        if damage == "version":
            meta["schema_version"] = 99
        elif damage == "question":
            meta["next_question"] = "Q-missing"
        elif damage == "checks":
            meta["checks"]["structure"] = "invented"
        elif damage in {"flow", "next_question", "missing-checks"}:
            del meta["checks" if damage == "missing-checks" else damage]
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


def discussion_file(root, records=(), **metadata):
    meta = dict(schema_version=1, document_type="questions", change_id=root.name, language="en")
    meta.update(metadata)
    path = root / "questions.md"
    write(path, meta, records)
    return path


def approved_bundle(tmp_path):
    root = project(tmp_path)
    report(tmp_path, root)
    decisions(root, [user(tmp_path, "document_approval")])
    return root


def test_open_blocker_prevents_readiness_without_revoking_approval(tmp_path):
    root = approved_bundle(tmp_path)
    discussion_file(root, [question()])
    result = review_status(tmp_path, root, "documents")
    assert not result["errors"]
    assert result["approval_status"]["approved"]
    assert not result["approval_status"]["ready"]
    assert result["discussion_status"]["open_questions"] == ["Q-mode"]
    assert result["discussion_status"]["blocking_questions"] == ["Q-mode"]
    assert not result["discussion_status"]["complete"]


def test_deferred_question_remains_open_without_blocking(tmp_path):
    root = approved_bundle(tmp_path)
    record = {**question(), "blocking": False, "reason": "Outside current scope", "return_at": "Before rollout"}
    discussion_file(root, [record])
    result = review_status(tmp_path, root, "documents")
    assert result["discussion_status"]["open_questions"] == ["Q-mode"]
    assert result["discussion_status"]["blocking_questions"] == []
    assert result["approval_status"]["ready"]
    del record["return_at"]
    discussion_file(root, [record])
    result = review_status(tmp_path, root, "documents")
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]
    assert result["errors"]


def test_resolved_question_requires_evidence(tmp_path):
    root = approved_bundle(tmp_path)
    record = {**question(), "status": "resolved"}
    discussion_file(root, [record])
    result = review_status(tmp_path, root, "documents")
    assert result["discussion_status"]["complete"] is False
    assert result["approval_status"]["ready"] is False
    (root / "decisions.md").write_text("# Decisions\n\n### Mode\nUser chose serial.\n", encoding="utf-8")
    record["resolution"] = "decisions.md#mode"
    discussion_file(root, [record])
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


@pytest.mark.parametrize("machine_exists", [False, True])
def test_markdown_checkpoint_cannot_shadow_questions(tmp_path, machine_exists):
    # Reuse real checkpoint files to detect accidental acceptance of state frontmatter.
    root = approved_bundle(tmp_path)
    discussion_file(root, [{**question(), "status": "resolved", "resolution": "design.md"}])
    meta = checkpoint(root)
    write(root / "state.md", meta, [question()])
    if not machine_exists:
        (root / "state.yaml").unlink()
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    from lib.documents import read_document, ValidationError
    with pytest.raises(ValidationError, match="Markdown state documents are unsupported"):
        read_document(root / "state.md")
    result = review_status(tmp_path, root, "documents")
    assert any(e["code"] == "state_recovery" for e in result["warnings"])
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("metadata", [{"change_id": "other"}, {"document_type": "state"}, {"schema_version": 99}, {"language": ""}, {"unexpected": True}])
def test_question_metadata_is_strict(tmp_path, metadata):
    root = approved_bundle(tmp_path)
    discussion_file(root, **metadata)
    result = review_status(tmp_path, root, "documents")
    assert result["errors"]
    assert not result["approval_status"]["ready"]


@pytest.mark.parametrize("content", [b"\xff", b"---\nbroken: [\n---\n", b"No frontmatter\n"])
def test_corrupt_discussion_is_not_complete(tmp_path, content):
    root = approved_bundle(tmp_path)
    path = discussion_file(root)
    path.write_bytes(content)
    result = review_status(tmp_path, root, "documents")
    assert result["errors"]
    assert not result["discussion_status"]["complete"]
    assert not result["approval_status"]["ready"]


def test_missing_checkpoint_blocks_readiness_without_revoking_approval(tmp_path):
    root = approved_bundle(tmp_path)
    (root / "state.yaml").unlink()
    (root / "state.md").unlink()
    result = review_status(tmp_path, root, "documents")
    assert result["warnings"][0]["code"] == "state_recovery"
    assert result["approval_status"]["approved"]
    assert not result["approval_status"]["ready"]
    assert "available question records only" in result["discussion_status"]["provenance"]


def test_discussion_files_do_not_change_review_snapshots(tmp_path):
    root = approved_bundle(tmp_path)
    report(tmp_path, root, lens="simplicity")
    before = review_status(tmp_path, root, "documents")["review_status"]["reports"]
    discussion_file(root, [question()])
    checkpoint(root)
    (root / "decisions.md").write_text("### Mode\nProposed by agent; awaiting user.\n", encoding="utf-8")
    assert before == review_status(tmp_path, root, "documents")["review_status"]["reports"]
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
