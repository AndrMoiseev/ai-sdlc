"""The behavior runner fails closed when independent evidence is incomplete."""
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("refactoring_runner", Path(__file__).resolve().parents[1] / "evals/run_refactoring.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def completed_run(root):
    root.mkdir()
    runner.write_json(root / "run.json", {"status": "completed", "returncode": 0, "error": None})
    runner.write_json(root / "preflight.json", {"status": "passed"})
    runner.write_json(root / "timing.json", {"duration_ms": None, "total_tokens": None})
    (root / "stdout.jsonl").write_text('{"type":"turn.completed"}\n', encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "response.md").write_text("Observed result", encoding="utf-8")
    return root


@pytest.mark.parametrize("missing", ["run.json", "preflight.json", "stdout.jsonl", "stderr.txt", "response.md", "timing.json"])
def test_refactoring_runner_requires_every_real_artifact(tmp_path, missing):
    root = completed_run(tmp_path / "run")
    (root / missing).unlink()
    with pytest.raises(ValueError, match="Missing real execution artifact"):
        runner.require_run(root)


@pytest.mark.parametrize("event", ['{"type":"turn.started"}', '{"type":"turn.completed"}\n{"type":"error"}', 'not-json'])
def test_refactoring_runner_shell_success_does_not_prove_model_completion(tmp_path, event):
    root = completed_run(tmp_path / "run")
    (root / "stdout.jsonl").write_text(event, encoding="utf-8")
    with pytest.raises(ValueError):
        runner.require_run(root)


@pytest.mark.parametrize("meta", [{"status": "error", "returncode": 0}, {"status": "completed", "returncode": 1},
                                  {"status": "completed", "returncode": 0, "error": "permission denied"}])
def test_refactoring_runner_rejects_unsuccessful_session_even_with_response(tmp_path, meta):
    root = completed_run(tmp_path / "run")
    runner.write_json(root / "run.json", meta)
    with pytest.raises(ValueError, match="Unsuccessful real execution"):
        runner.require_run(root)


def test_refactoring_runner_independent_grading_preserves_false_and_recomputes_summary():
    text = json.dumps({"expectations": [{"text": "Required output", "dimension": "Completeness",
                                        "evidence": "action.md records a promise, but no requested document was produced.", "passed": False}],
                       "summary": {"passed": 999}})
    result = runner.parse_grading(text, ["Required output"])
    assert result["summary"] == {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0}
    assert result["failing"][0]["passed"] is False


@pytest.mark.parametrize("row", [
    {"text": "Required output", "dimension": "Completeness", "evidence": "", "passed": True},
    {"text": "Required output", "dimension": "Completeness", "evidence": "No proof", "passed": "false"},
    {"text": "Required output", "dimension": "Invented", "evidence": "No proof", "passed": True},
    {"text": "Required output", "dimension": "Completeness", "passed": True, "evidence": "Verdict first"},
    {"text": "Different assertion", "dimension": "Completeness", "evidence": "Scope narrowed", "passed": True},
])
def test_refactoring_runner_rejects_invalid_or_narrowed_grading(row):
    with pytest.raises(ValueError):
        runner.parse_grading(json.dumps({"expectations": [row]}), ["Required output"])


def test_refactoring_runner_freezes_complete_package_membership(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "SKILL.md").write_text("old", encoding="utf-8")
    record = {"path": str(package), "files": runner.inventory(package)}
    assert runner.verify_package(record) == package
    (package / "extra.md").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="membership changed"):
        runner.verify_package(record)


def test_refactoring_runner_never_reuses_an_existing_workspace(tmp_path):
    first = runner.make_workspace(tmp_path, "same-case")
    second = runner.make_workspace(tmp_path, "same-case")
    assert first != second
    assert first.is_dir() and second.is_dir()


def test_refactoring_runner_rejects_repository_ancestor_candidate(tmp_path):
    skill = tmp_path / ".agents/skills/sdd-spec/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("candidate", encoding="utf-8")
    with pytest.raises(ValueError, match="ancestor exposes"):
        runner.make_workspace(tmp_path / "fixtures", "case")


@pytest.mark.parametrize("path", ["../escape", "/escape"])
def test_refactoring_runner_fixture_paths_stay_within_workspace(tmp_path, path):
    with pytest.raises(ValueError, match="escapes"):
        runner.relative_path(tmp_path, path)


def test_refactoring_runner_script_paths_and_arguments_remain_distinct_data(monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda name: "C:/Tools/uv.exe")
    script = Path("folder with spaces/script.py")
    command = runner.uv_command(script, "--fixture", "a b; c")
    assert command == ["C:/Tools/uv.exe", "run", "--locked", "--script", str(script), "--fixture", "a b; c"]


def required_scenarios():
    return [{"id": index, "name": name, "prompt": "Do the task", "assertions": ["Observed output"],
             "repetitions": 5 if name == "completeness-pressure-micro" else 1}
            for index, name in enumerate(sorted(runner.REQUIRED_SCENARIOS), 1)]


def test_refactoring_runner_requires_complete_scenario_set():
    scenarios = required_scenarios()
    runner.validate_scenarios(scenarios)
    for omitted in scenarios:
        with pytest.raises(ValueError, match="every required"):
            runner.validate_scenarios([case for case in scenarios if case is not omitted])


def test_refactoring_runner_pressure_requires_five_fresh_repetitions():
    scenarios = required_scenarios()
    next(case for case in scenarios if case["name"] == "completeness-pressure-micro")["repetitions"] = 4
    with pytest.raises(ValueError, match="five fresh"):
        runner.validate_scenarios(scenarios)


def test_refactoring_runner_rejects_prior_run_binding(tmp_path):
    output = completed_run(tmp_path / "execution")
    expected = {"run_id": "current", "started_ns": 0}
    runner.write_json(tmp_path / "execution-binding.json", {"run_id": "previous", "started_ns": 0})
    with pytest.raises(ValueError, match="Stale or missing"):
        runner.require_run(output, expected)


def test_refactoring_runner_rejects_old_artifacts_even_with_current_binding(tmp_path):
    output = completed_run(tmp_path / "execution")
    expected = {"run_id": "current", "started_ns": runner.time.time_ns() + 10_000_000_000}
    runner.write_json(tmp_path / "execution-binding.json", expected)
    with pytest.raises(ValueError, match="Stale execution artifact"):
        runner.require_run(output, expected)


def test_refactoring_runner_accepts_current_complete_evidence(tmp_path):
    output = completed_run(tmp_path / "execution")
    expected = {"run_id": "current", "started_ns": 0}
    runner.write_json(tmp_path / "execution-binding.json", expected)
    assert runner.require_run(output, expected)["returncode"] == 0

@pytest.mark.parametrize("relative", ["skills/results", "packages/spec/results", ".agents/results"])
def test_refactoring_runner_keeps_runtime_state_outside_packages(tmp_path, relative):
    with pytest.raises(ValueError, match="outside skill"):
        runner.require_external_storage(tmp_path / relative, [tmp_path / "packages/spec"])


def test_refactoring_runner_accepts_external_retained_storage(tmp_path):
    storage = tmp_path / "retained-results"
    assert runner.require_external_storage(storage, [tmp_path / "packages/spec"]) == storage


def test_refactoring_runner_fixture_copies_complete_dependencies_and_selected_variant(tmp_path):
    roots = {}
    for name in ("old_skill", "sdd-shared", "humanizer-ru", "candidate"):
        package = tmp_path / "sources" / name
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(name, encoding="utf-8")
        (package / "resource.md").write_text("complete resource", encoding="utf-8")
        roots[name] = package
    for variant in ("old_skill", "without_skill", "with_skill"):
        workspace = runner.make_workspace(tmp_path / "fixtures", variant)
        manifest = runner.prepare_fixture(workspace, {"files": {"src/example.py": "pass\n"}}, roots, roots["candidate"], variant)
        assert (workspace / ".agents/skills/sdd-shared/resource.md").read_text() == "complete resource"
        assert (workspace / ".agents/skills/humanizer-ru/resource.md").is_file()
        skill = workspace / ".agents/skills/sdd-spec/SKILL.md"
        if variant == "without_skill":
            assert not skill.exists()
            assert manifest["expected_missing_files"] == [".agents/skills/sdd-spec/SKILL.md"]
        else:
            assert skill.read_text() == ("old_skill" if variant == "old_skill" else "candidate")
            assert ".agents/skills/sdd-spec/resource.md" in manifest["required_files"]

def test_refactoring_runner_can_reuse_selected_system_interpreter(monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda name: "uv")
    assert runner.uv_command(Path("script.py"), "arg", python="Python with spaces/python.exe") == [
        "uv", "run", "--python", "Python with spaces/python.exe", "--locked", "--script", "script.py", "arg"]