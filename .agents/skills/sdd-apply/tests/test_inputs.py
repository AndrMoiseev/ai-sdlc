from lib.repository import repository
from repository_support import stage as stage_files
import pytest
from lib.inputs import validate, spec_modules

from conftest import SPEC, document


def call(project):
    return validate(project, "demo", {"text": "Implement", "source": "message"}, SPEC)


def test_approved_and_preserves_dirty(project):
    # Reuse the existing admission fixture and shared CLI adapter: a valid
    # approval must admit execution without reports or legacy review waivers.
    change = project / "sdd/changes/demo"
    docs = spec_modules(SPEC)
    decisions = docs.read_document(change / "review/decisions.md")
    approvals = [record for record in decisions.records if record["kind"] != "review_waiver"]
    document(change / "review/decisions.md", decisions.meta, approvals)
    checkpoint = docs.read_document(change / "state.md")
    checkpoint.meta["approval_refs"] = [record["id"] for record in approvals]
    document(change / "state.md", checkpoint.meta, checkpoint.records)
    approval = next(record for record in approvals if record["kind"] == "plan_approval")
    instruction = {"text": approval["response"], "source": f"review/decisions.md#{approval['id']}"}
    (project / "foreign.txt").write_bytes(b"staged")
    stage_files(project, "foreign.txt")
    (project / "foreign.txt").write_bytes(b"unstaged")
    (project / "untracked.txt").write_bytes(b"keep")
    before = (repository(project).head(), repository(project).index_patch(), (project / "foreign.txt").read_bytes())
    result = validate(project, "demo", instruction, SPEC)
    assert result["tasks"][0]["id"] == "TASK-one"
    assert result["instruction"] == instruction
    for stage in ("documents", "plan"):
        assert result["checks"][stage]["approval_status"]["ready"]
        assert not result["checks"][stage]["review_status"]["complete"]
        assert set(result["checks"][stage]["review_status"]["coverage"].values()) == {"missing"}
    assert before == (repository(project).head(), repository(project).index_patch(), (project / "foreign.txt").read_bytes())
    assert "working_patch" not in result and "index_patch" not in result
    assert (project / "untracked.txt").read_bytes() == b"keep"


@pytest.mark.parametrize("mutation", ["approval", "stale", "question", "missing"])
def test_invalid(project, mutation):
    change = project / "sdd/changes/demo"
    if mutation == "approval":
        (change / "review/decisions.md").unlink()
    elif mutation == "stale":
        with (change / "tasks.md").open("a") as stream:
            stream.write("Changed plan\n")
    elif mutation == "question":
        with (change / "state.md").open("a") as stream:
            stream.write("\n### Open question\n\n```yaml\nsdd_record: question\nid: Q-open\ntext: Resolve\nblocking: true\nstatus: open\n```\n")
    else:
        (change / "tasks.md").unlink()
    before = {str(p): p.read_bytes() for p in change.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        call(project)
    assert before == {str(p): p.read_bytes() for p in change.rglob("*") if p.is_file()}


def test_missing_dependency(project):
    with pytest.raises(ValueError, match="sdd-shared"):
        validate(project, "demo", {"text": "Do", "source": "message"}, project / "missing")


def test_incompatible_shared_api_is_actionable(project, tmp_path):
    import json
    root = tmp_path / "incompatible"
    root.mkdir()
    (root / "api.json").write_text(json.dumps({"api_version": 2}))
    with pytest.raises(ValueError, match="Incompatible sdd-shared API"):
        validate(project, "demo", {"text": "Do", "source": "message"}, sdd_shared=root)
