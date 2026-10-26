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


@pytest.fixture
def frozen_runtime_packages(tmp_path):
    """Actual files keep the copy operation and its manifests under test."""
    frozen = tmp_path / "frozen inputs"
    runtime = {
        "SKILL.md": "Read references/runtime-setup.md and flows/draft.md.\n",
        "references/runtime-setup.md": "Use scripts/check.py with its adjacent lock.\n",
        "references/document-format-refactoring.md": "Runtime refactoring contract.\n",
        "references/reviewer-plan.md": "Runtime independent plan review contract.\n",
        "references/patterns.md": "Runtime editorial patterns.\n",
        "flows/draft.md": "Read templates/design.md.\n",
        "templates/design.md": "Runtime document template.\n",
        "scripts/check.py": "from shared import validate\n",
        "scripts/check.py.lock": "version = 1\n",
        "scripts/shared.py": "def validate(): return []\n",
        "scripts/snapshot.py": "print('snapshot')\n",
        "scripts/snapshot.py.lock": "version = 1\n",
        "scripts/resolve_agent.py": "print('runtime role resolution')\n",
        "scripts/resolve_agent.py.lock": "version = 1\n",
        "scripts/lint.py": "print('runtime editorial lint')\n",
        "agents/openai.yaml": "policy: {allow_implicit_invocation: false}\n",
        "schemas/refactoring.schema.json": '{"type": "object"}\n',
        "api.json": '{"version": 1}\n',
        ".gitignore": "__pycache__/\n",
        "references/.runtime-resource": "Required hidden resource.\n",
        "assets/fixture.bin": "Binary runtime resource: \u0000\u0001\n",
    }
    answer = "GRADER_ONLY_EXACT_ASSERTION_DO_NOT_EXPOSE"
    development = {
        "evals/evals.json": json.dumps({"prompt": "task", "expectations": [answer]}),
        "evals/nested/.heldout.json": json.dumps({"expected_output": answer}),
        "evals/refactoring.md": answer,
        "tests/test_expected.py": f"assert result == {answer!r}\n",
        "tests/fixtures/answers.json": json.dumps([answer]),
        "eval-viewer/answers.html": answer,
        "agents/grader.md": answer,
        "agents/comparator.md": answer,
        "agents/analyzer.md": answer,
        "agents/bineval.md": answer,
        "scripts/test.py": answer,
        "scripts/test.py.lock": answer,
        "scripts/prepare_subagent_eval.py": answer,
        "scripts/prepare_subagent_eval.py.lock": answer,
    }
    roots, records = {}, {}
    for name in ("old_skill", "candidate", "sdd-shared", "humanizer-ru", "sdd-skill-conductor"):
        package = frozen / name
        for relative, content in (runtime | development).items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        roots[name] = package
        records[name] = {"path": str(package), "files": runner.inventory(package)}
    runner.write_json(frozen / "fixture-spec.json", {"packages": records, "assertions": [answer]})
    runner.write_json(frozen / "split.json", {"train_ids": [1], "heldout_ids": [2]})
    return frozen, roots, records, runtime, development, answer


def test_refactoring_runner_runtime_copies_hide_answers_preserve_dependencies_and_frozen_inputs(
        tmp_path, frozen_runtime_packages):
    frozen, roots, records, runtime, development, answer = frozen_runtime_packages
    original_bytes = {path.relative_to(frozen): path.read_bytes()
                      for path in frozen.rglob("*") if path.is_file()}
    before = runner.inventory(frozen)
    dependency_copies = []
    selected_copies = []
    scenario = {"files": {"src/product.py": "product_id = 1\n"}}

    for variant in ("with_skill", "old_skill", "without_skill"):
        workspace = runner.make_workspace(tmp_path / "fixtures", variant)
        manifest = runner.prepare_fixture(workspace, scenario, roots, roots["candidate"], variant)
        installed = workspace / ".agents/skills"
        packages = ["sdd-shared", "humanizer-ru"]
        if variant != "without_skill":
            packages.append("sdd-spec")
        assert {path.name for path in installed.iterdir()} == set(packages)
        expected_manifest = {"src/product.py"}
        for name in packages:
            target = installed / name
            assert set(runner.inventory(target)) == set(runtime)
            for relative, content in runtime.items():
                assert (target / relative).read_bytes() == content.encode("utf-8")
                expected_manifest.add(f".agents/skills/{name}/{relative}")
            for relative in development:
                assert not (target / relative).exists()
        assert set(manifest["required_files"]) == expected_manifest
        assert all(answer.encode("utf-8") not in path.read_bytes()
                   for path in workspace.rglob("*") if path.is_file())
        dependency_copies.append({name: runner.inventory(installed / name)
                                  for name in ("sdd-shared", "humanizer-ru")})
        if variant == "without_skill":
            assert not (installed / "sdd-spec").exists()
            assert manifest["expected_missing_files"] == [".agents/skills/sdd-spec/SKILL.md"]
        else:
            selected_copies.append(runner.inventory(installed / "sdd-spec"))
            assert manifest["expected_missing_files"] == []

        # Source inventories still include development assets; nothing is sanitized in place.
        assert runner.inventory(frozen) == before
        assert {path.relative_to(frozen): path.read_bytes()
                for path in frozen.rglob("*") if path.is_file()} == original_bytes
        for name, record in records.items():
            assert runner.verify_package(record) == roots[name]
            assert "evals/evals.json" in record["files"]
    assert dependency_copies[0] == dependency_copies[1] == dependency_copies[2]
    assert selected_copies[0] == selected_copies[1]


@pytest.mark.parametrize("damage", ["missing", "changed", "extra"])
def test_refactoring_runner_rejects_damaged_runtime_copy(tmp_path, frozen_runtime_packages, monkeypatch, damage):
    _, roots, _, _, _, _ = frozen_runtime_packages
    source = roots["candidate"]
    before = runner.inventory(source)
    copytree = runner.shutil.copytree

    def damaged_copy(source, target, *args, **kwargs):
        result = copytree(source, target, *args, **kwargs)
        if Path(target) == tmp_path / "runtime":
            resource = Path(target) / "references/.runtime-resource"
            if damage == "missing":
                resource.unlink()
            elif damage == "changed":
                resource.write_bytes(b"changed")
            else:
                (Path(target) / "unexpected.md").write_bytes(b"extra")
        return result

    monkeypatch.setattr(runner.shutil, "copytree", damaged_copy)
    with pytest.raises(ValueError, match="Runtime package bytes or membership changed"):
        runner.copy_runtime_package(source, tmp_path / "runtime")
    assert runner.inventory(source) == before
