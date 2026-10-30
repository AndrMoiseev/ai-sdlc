"""Spec assignment recovery and instruction/fixture contracts, without agent runs."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "evals/fixtures/explorer.json").read_text(encoding="utf-8"))
spec = importlib.util.spec_from_file_location("spec_explorer", ROOT / "scripts/explorer.py")
explorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(explorer)


def packet(kind, project, directory):
    return json.loads(json.dumps(FIXTURE[kind]).replace("{project}", str(project).replace("\\", "/"))
                      .replace("{artifacts}", str(directory).replace("\\", "/")))


def result_for(assignment):
    result = {field: deepcopy(assignment[field]) for field in ("id", "kind", "scope", "basis")}
    result.update(deepcopy(FIXTURE["research_result"]))
    result["launch"] = deepcopy(FIXTURE["launch"])
    if assignment["kind"] == "checks":
        result.update(summary={"exit_code": 0}, raw_artifacts=[], diagnosis="Structure only")
    return result


def capabilities():
    return {name: {"available": True, "trace": "fixture-only: observed " + name}
            for name in ("launch", "read", "write_artifacts", "run_command")}


def test_external_recovery_preserves_checkpoint_and_sources(bundle, tmp_path, monkeypatch):
    # Real files are necessary for the absolute-reference/digest/deletion boundary;
    # reuse the existing spec bundle, with all scenario combinations in memory below.
    project, change, _, _ = bundle
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    monkeypatch.setattr(explorer.tempfile, "gettempdir", lambda: str(tmp_path))
    directory = explorer.create_directory(project, [ROOT.parent], tmp_path / "cache")
    assert directory.is_absolute() and directory.parent == tmp_path
    assert not directory.is_relative_to(project)
    assignment = packet("research", project, directory)
    request = explorer.save_request(directory, assignment, {"role": "sdd-spec.explorer"}, capabilities())
    launch = explorer.write_artifact(directory, assignment["id"] + ".launch.json", FIXTURE["launch"])
    pending = explorer.recover(request, None, assignment["basis"], launch)
    assert pending["status"] == "incomplete"
    assert pending["launch"] == FIXTURE["launch"]
    result = explorer.validate_result(assignment, result_for(assignment))
    reference = explorer.write_artifact(directory, assignment["id"] + ".result.json", result)
    restored = explorer.recover(request, reference, assignment["basis"], launch)
    assert restored["status"] == "completed"
    assert restored["request"]["assignment"] == assignment
    assert restored["result"]["sources"] == FIXTURE["research_result"]["sources"]
    assert restored["result"]["scope"]["work"] is None
    assert restored["result"]["scope"]["task"] is None
    assert not (change / "execution").exists()
    for ref in (request, launch, reference):
        assert Path(ref["path"]).is_absolute()
        assert hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest() == ref["sha256"]
    Path(reference["path"]).write_text("{}", encoding="utf-8")
    assert "digest" in explorer.recover(request, reference, assignment["basis"], launch)["reason"]
    Path(reference["path"]).unlink()
    assert explorer.recover(request, reference, assignment["basis"], launch)["status"] == "unavailable"
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("excluded", ["project", "skills", "cache"])
def test_temp_api_inside_excluded_root_stops_before_creation(monkeypatch, excluded):
    base = Path.cwd().anchor
    roots = {name: Path(base) / name for name in ("project", "skills", "cache")}
    monkeypatch.setattr(explorer.tempfile, "gettempdir", lambda: str(roots[excluded] / "temp"))
    monkeypatch.setattr(explorer.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("Must stop before write"))
    with pytest.raises(ValueError, match="inside project, skills or uv cache"):
        explorer.create_directory(roots["project"], [roots["skills"]], roots["cache"])


def test_temp_creation_uses_environment_api_and_unique_directory(monkeypatch):
    base = Path(Path.cwd().anchor) / "environment-temp"
    calls = []
    monkeypatch.setattr(explorer.tempfile, "gettempdir", lambda: str(base))
    def make(**kwargs):
        calls.append(kwargs)
        return str(base / (kwargs["prefix"] + str(len(calls))))
    monkeypatch.setattr(explorer.tempfile, "mkdtemp", make)
    first = explorer.create_directory(base.parent / "project", [ROOT.parent], base.parent / "cache")
    second = explorer.create_directory(base.parent / "project", [ROOT.parent], base.parent / "cache")
    assert first != second
    assert calls == [{"prefix": "sdd-spec-explorer-", "dir": base}] * 2


@pytest.mark.parametrize("kind", ["research", "checks"])
def test_fixture_assignments_distinguish_scope_and_readonly_outputs(kind):
    assignment = packet(kind, Path.cwd(), Path.cwd() / "fixture-artifacts")
    contract = explorer.load(explorer.locate(), "explorer")
    assert contract.validate_assignment(assignment) == assignment
    assert assignment["scope"]["task"] is None
    assert bool(assignment["basis"]) and bool(assignment["read_scope"])
    assert ("question" in assignment) == (kind == "research")
    assert ("check_ids" in assignment) == (kind == "checks")
    assert explorer.validate_result(assignment, result_for(assignment))["basis"] == assignment["basis"]


@pytest.mark.parametrize("field", ["id", "kind", "scope", "basis"])
def test_foreign_result_cannot_restore_completion(field):
    assignment = deepcopy(FIXTURE["research"])
    result = result_for(assignment)
    result[field] = "foreign"
    with pytest.raises(ValueError, match="foreign or stale"):
        explorer.validate_result(assignment, result)


@pytest.mark.parametrize("fault", ["request_missing", "result_missing", "launch_missing", "stale",
                                   "launch_mismatch", "damaged_json"])
def test_recovery_failure_is_unavailable_not_summary_proof(monkeypatch, fault):
    assignment = deepcopy(FIXTURE["research"])
    result = result_for(assignment)
    values = {"request": {"assignment": assignment}, "result": result, "launch": FIXTURE["launch"]}
    def read(reference):
        if fault == reference + "_missing":
            raise FileNotFoundError(reference)
        if fault == "damaged_json" and reference == "result":
            raise ValueError("Malformed JSON")
        return values[reference]
    monkeypatch.setattr(explorer, "read_artifact", read)
    basis = {"changed": True} if fault == "stale" else assignment["basis"]
    if fault == "launch_mismatch":
        result["launch"] = {"context_id": "other", "trace": "other launch"}
    restored = explorer.recover("request", "result", basis, "launch")
    assert restored["status"] == "unavailable"
    assert restored["result"] is None
    assert restored["reason"]


def test_capability_or_output_failure_prevents_request_write(monkeypatch):
    directory = Path.cwd() / "artifacts"
    assignment = packet("checks", Path.cwd(), directory)
    monkeypatch.setattr(explorer, "write_artifact", lambda *args: pytest.fail("Unexpected write"))
    observations = capabilities()
    observations["run_command"]["available"] = False
    with pytest.raises(ValueError, match="capabilities unavailable"):
        explorer.save_request(directory, assignment, {"role": "sdd-spec.explorer"}, observations)
    assignment["outputs"] = [str(Path.cwd() / "design.md")]
    with pytest.raises(ValueError, match="outputs must stay"):
        explorer.save_request(directory, assignment, {"role": "sdd-spec.explorer"}, capabilities())


def test_explorer_fixture_and_procedure_are_prepared_not_executed():
    assert set(FIXTURE["criteria"]) == {"AC-explorer-research", "AC-explorer-assignment",
                                       "AC-spec-research-handoff", "AC-spec-check-delegation"}
    assert len(FIXTURE["sources"]) == 2
    assert [case["exit_code"] for case in FIXTURE["check_cases"]] == [0, 1, 2, None]
    text = (ROOT / "evals/manual.md").read_text(encoding="utf-8")
    assert "fixtures/explorer.json" in text
    for criterion in FIXTURE["criteria"]:
        assert criterion in text
    assert "Эвал не запускался" in text
    assert "отдельного явного поручения пользователя" in text


def test_flows_reach_single_assignment_and_recovery_contract():
    for name in ("explore", "draft", "revise", "plan", "resume"):
        text = (ROOT / "flows" / (name + ".md")).read_text(encoding="utf-8")
        assert "../references/explorer.md" in text, name
    for name in ("codex", "claude-code", "generic", "runtime-setup", "resume-recovery", "checkpoint"):
        assert "explorer.md" in (ROOT / "references" / (name + ".md")).read_text(encoding="utf-8"), name
    contract = (ROOT / "references/explorer.md").read_text(encoding="utf-8")
    for obligation in ("sdd-spec.explorer", "read_scope", "outputs", "sources", "basis", "SHA-256",
                       "state.yaml.document_links", "incomplete", "unavailable", "Exit 0 не создаёт USER"):
        assert obligation in contract
    assert "explorer" in (ROOT / "templates/state.md").read_text(encoding="utf-8")


def test_documents_and_plan_exit_zero_never_create_user_approval(tmp_path, command_main):
    # Reuse the existing document fixture and in-process CLI adapter: filesystem
    # evidence is required to prove that consuming a check never writes USER records.
    from test_check_command import create_project, hashes
    create_project(tmp_path)
    before = hashes(tmp_path)
    for stage in ("documents", "plan"):
        completed = command_main(tmp_path, stage=stage)
        assert completed.returncode == 0, completed.stdout
        output = json.loads(completed.stdout)
        assert output["approval_status"]["approved"] is False
        assert output["approval_status"]["ready"] is False
    assert hashes(tmp_path) == before
