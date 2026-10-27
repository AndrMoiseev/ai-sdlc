"""Deterministic runner contracts with synthetic evidence; never call a model."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def runner():
    path = Path(__file__).resolve().parents[1] / "evals/run_refactoring_tests.py"
    spec = importlib.util.spec_from_file_location("boundary_behavior_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packages(root, runner, marker):
    for name in runner.PACKAGES:
        package = root / name
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(marker + name, encoding="utf-8")
        (package / "tests").mkdir()
        (package / "tests/answers.txt").write_text("private grading answers", encoding="utf-8")
    return root


def isolation(runner, root, manifest):
    path = root / "isolation.json"
    runner.write(path, {"status": "passed", "manifest_sha256": runner.sha256(root / "manifest.json"),
        "host_trace": "synthetic-contract-test; no actual host launched", "exposed_candidate_to_controls": False,
        "run_ids": [run["id"] for run in manifest["runs"]]})
    return path


def test_full_pair_matrix_has_every_scenario_role_variant_and_repetition(runner):
    matrix = list(runner.scenario_matrix(5))
    expected = {(scenario, role, variant, repeat)
                for scenario in ("merge-mixed", "structural-retirement", "split-contract", "persistent-move")
                for role in ("executor", "reviewer")
                for variant in ("with_skill", "old_skill", "no_guidance")
                for repeat in range(1, 6)}
    assert len(matrix) == 120 and set(matrix) == expected


def test_prepare_freezes_dependency_parity_and_excludes_grading_files(runner, tmp_path, monkeypatch):
    # Repetition counts belong to the pure matrix contract. Exercise each package
    # variant once, retaining both roles and the different source branches.
    cases = [("merge-mixed", "executor", "with_skill", 1),
             ("split-contract", "reviewer", "old_skill", 1),
             ("structural-retirement", "executor", "no_guidance", 1)]
    monkeypatch.setattr(runner, "scenario_matrix", lambda repetitions: iter(cases))
    candidate = packages(tmp_path / "candidate", runner, "candidate-")
    control = packages(tmp_path / "control", runner, "old-")
    root = tmp_path / "prepared"
    manifest = runner.prepare(root, candidate, control, 5)
    assert len(manifest["runs"]) == 3
    assert len({run["id"] for run in manifest["runs"]}) == 3
    assert runner.preflight(root, isolation(runner, root, manifest)) == manifest
    for run in manifest["runs"]:
        skills = root / run["fixture"] / ".agents/skills"
        assert not list(skills.rglob("answers.txt"))
        if run["variant"] == "no_guidance":
            assert not skills.exists()
        else:
            prefix = "candidate-" if run["variant"] == "with_skill" else "old-"
            assert (skills / "sdd-apply/SKILL.md").read_text() == prefix + "sdd-apply"
            assert (skills / "sdd-shared/SKILL.md").read_text() == "old-sdd-shared"
        assert not (root / run["fixture"] / "grading.json").exists()
        source = (root / run["fixture"] / "test_transfer.py").read_text()
        assert ("def test_rollback" in source) == (run["scenario"] != "split-contract")
        assert ("assert 'validate('" in source) == (run["scenario"] == "merge-mixed")
        prompt = (root / run["input"] / "prompt.txt").read_text()
        assert f"Act as the {run['role']} for task.md" in prompt
        assert ("Read .agents/skills/" in prompt) == (run["variant"] != "no_guidance")


def test_prepare_rejects_missing_package_and_insufficient_repetitions(runner, tmp_path):
    with pytest.raises(ValueError, match="five fresh"):
        runner.prepare(tmp_path / "out", tmp_path / "new", tmp_path / "old", 4)
    with pytest.raises(ValueError, match="Missing complete dependency"):
        runner.prepare(tmp_path / "out", tmp_path / "new", tmp_path / "old", 5)


@pytest.fixture(scope="module")
def evidence_template(runner, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("behavior-evidence")
    runs = []
    for variant in runner.VARIANTS:
        for repeat in range(1, 6):
            ident = f"merge-mixed-executor-{variant}-{repeat}"
            output = f"results/eval-merge-mixed-executor/{variant}/run-{repeat}"
            runs.append(dict(id=ident, scenario="merge-mixed", role="executor", variant=variant,
                             repeat=repeat, output=output))
            directory = tmp_path / output
            directory.mkdir(parents=True)
            for name, content in (("response.md", "synthetic response"), ("stdout.jsonl", '{"synthetic":true}\n'), ("stderr.txt", "")):
                (directory / name).write_text(content, encoding="utf-8")
            runner.write(directory / "run.json", {"status": "completed", "returncode": 0, "harness": "codex", "model": "synthetic"})
            runner.write(directory / "timing.json", {"total_duration_seconds": 0.1, "total_tokens": None})
            runner.write(directory / "preflight.json", {"status": "passed"})
            runner.write(directory / "grading.json", {"expectations": [dict(text=text, passed=True, evidence="Synthetic contract fixture evidence")
                for text in runner.SCENARIOS["merge-mixed"]["expectations"]]})
            runner.write(directory / "grader.json", {"independent": True, "context_id": "synthetic-grader",
                "executor_context_id": ident, "host_trace": "synthetic independent grader",
                "sha256": {name: runner.sha256(directory / name) for name in ("response.md", "stdout.jsonl", "run.json", "timing.json")}})
    runner.write(tmp_path / "manifest.json", {"repetitions": 5, "runs": runs})
    runner.write(tmp_path / "preflight.json", {"status": "passed", "manifest_sha256": runner.sha256(tmp_path / "manifest.json"),
        "harness": "codex", "model": "synthetic"})
    runner.write(tmp_path / "benchmark.json", {"synthetic": True})
    (tmp_path / "review.html").write_text("<p>Synthetic viewer</p>", encoding="utf-8")
    files, directories = {}, set()
    for path in tmp_path.rglob("*"):
        relative = path.relative_to(tmp_path)
        if path.is_dir():
            directories.add(relative)
        else:
            files[relative] = path.read_bytes(), path.stat().st_mode
    return tmp_path, tmp_path / runs[0]["output"], files, directories


@pytest.fixture
def evidence(runner, evidence_template, monkeypatch):
    from working_copy import restore
    monkeypatch.setattr(runner, "SCENARIOS", {"merge-mixed": runner.SCENARIOS["merge-mixed"]})
    monkeypatch.setattr(runner, "ROLES", ("executor",))
    root, output, files, directories = evidence_template
    restore(root, files, directories)
    return root, output


def test_complete_synthetic_evidence_validates_without_model(runner, evidence):
    root, _ = evidence
    assert runner.verify_evidence(root) == {"status": "passed", "runs": 15,
        "manifest_sha256": runner.sha256(root / "manifest.json")}


@pytest.mark.parametrize("damage,message", [
    ("missing-log", "Missing"), ("failed-run", "Failed or unavailable"),
    ("stale-grade", "stale"), ("same-grader", "Independent grading"),
    ("missing-assertion", "grading assertions"), ("failed-assertion", "Candidate behavior failed"),
    ("wrong-model", "same harness/model"), ("missing-viewer", "Missing final review"),
    ("short-matrix", "Incomplete or duplicate"), ("empty-trace", "trace is empty")])
def test_behavior_evidence_fails_closed(runner, evidence, damage, message):
    root, output = evidence
    if damage == "missing-log":
        (output / "stdout.jsonl").unlink()
    elif damage == "stale-grade":
        (output / "response.md").write_text("changed response", encoding="utf-8")
    elif damage == "empty-trace":
        (output / "stdout.jsonl").write_text("", encoding="utf-8")
    elif damage == "missing-viewer":
        (root / "review.html").unlink()
    elif damage == "short-matrix":
        manifest = runner.read(root / "manifest.json")
        manifest["runs"].pop()
        runner.write(root / "manifest.json", manifest)
        preflight = runner.read(root / "preflight.json")
        preflight["manifest_sha256"] = runner.sha256(root / "manifest.json")
        runner.write(root / "preflight.json", preflight)
    else:
        filename = "run.json" if damage in {"failed-run", "wrong-model"} else "grader.json" if damage == "same-grader" else "grading.json"
        data = runner.read(output / filename)
        if damage == "failed-run":
            data["status"] = "failed"
        elif damage == "wrong-model":
            data["model"] = "different-model"
        elif damage == "same-grader":
            data["context_id"] = data["executor_context_id"]
        elif damage == "missing-assertion":
            data["expectations"].pop()
        else:
            data["expectations"][0]["passed"] = False
        runner.write(output / filename, data)
    with pytest.raises(ValueError, match=message):
        runner.verify_evidence(root)


def test_actual_run_refuses_unverified_host_isolation_before_subprocess(runner, tmp_path, monkeypatch):
    runner.write(tmp_path / "manifest.json", {"runs": []})
    runner.write(tmp_path / "isolation.json", {"status": "unavailable"})
    calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="Isolation observation"):
        runner.run_sessions(tmp_path, tmp_path / "isolation.json", tmp_path, "python", "codex", "synthetic")
    assert calls == []


def test_launcher_uses_locked_argument_array_and_stops_at_first_failure(runner, tmp_path, monkeypatch):
    from types import SimpleNamespace
    manifest = {"runs": [dict(id="one", input="inputs/one", fixture="fixtures/one", output="results/one", role="executor"),
                         dict(id="two", input="inputs/two", fixture="fixtures/two", output="results/two", role="reviewer")]}
    runner.write(tmp_path / "manifest.json", manifest)
    runner.write(tmp_path / "isolation.json", {"status": "synthetic"})
    conductor = tmp_path / "conductor"
    (conductor / "scripts").mkdir(parents=True)
    (conductor / "scripts/run_task.py").write_text("# synthetic", encoding="utf-8")
    (conductor / "scripts/run_task.py.lock").write_text("# synthetic", encoding="utf-8")
    monkeypatch.setattr(runner, "preflight", lambda *args: manifest)
    calls = []
    def failed(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(runner.subprocess, "run", failed)
    python = tmp_path / "python executable.exe"
    with pytest.raises(ValueError, match="Behavior execution failed: one"):
        runner.run_sessions(tmp_path, tmp_path / "isolation.json", conductor, python, "codex", "synthetic")
    assert len(calls) == 1
    command, options = calls[0]
    assert command[:7] == ["uv", "run", "--python", str(python.resolve()), "--locked", "--script", str((conductor / "scripts/run_task.py").resolve())]
    assert command[-1] == "--allow-writes"
    assert options == {"shell": False, "check": False}
    assert not (tmp_path / "grading-request.json").exists()
