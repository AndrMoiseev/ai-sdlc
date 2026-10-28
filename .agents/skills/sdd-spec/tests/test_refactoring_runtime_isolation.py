"""Exercise real scenario oracles against disposable runtime package copies.

The old package here tests copying, not historical agent behavior. All sources
are repository/bundle relative; no retained private eval workspace is needed.
"""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("isolation_runner", SKILL / "evals/run_refactoring.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
SCENARIOS = [case for case in runner.read_json(SKILL / "evals/evals.json")["evals"]
             if case["id"] in range(101, 110)]
VARIANTS = ("old_skill", "with_skill", "without_skill")


def file_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture(scope="module")
def frozen_inputs(tmp_path_factory):
    humanizer = SKILL.parent / "humanizer-ru"
    if not humanizer.is_dir():
        humanizer = SKILL.parents[1] / ".agents/skills/humanizer-ru"
    assert (humanizer / "SKILL.md").is_file(), "Complete bundle needs humanizer-ru"
    sources = {"old_skill": SKILL, "candidate": SKILL,
               "sdd-shared": SKILL.parent / "sdd-shared", "humanizer-ru": humanizer}
    frozen = tmp_path_factory.mktemp("complete-frozen-inputs")
    roots = {}
    for name, source in sources.items():
        roots[name] = frozen / name
        shutil.copytree(source, roots[name])
    # Freeze full inputs, including their real eval/test assets. The split is a
    # local copy-contract fixture; it never replaces the operator's frozen split.
    records = {name: {"path": str(root), "files": runner.inventory(root)}
               for name, root in roots.items()}
    runner.write_json(frozen / "fixture-spec.json", {"packages": records, "scenarios": SCENARIOS})
    runner.write_json(frozen / "split.json", {"train_ids": list(range(101, 106)),
                                             "heldout_ids": list(range(106, 110))})
    return frozen, roots, records, file_bytes(frozen)


def test_refactoring_runtime_isolation_covers_every_actual_scenario():
    assert [case["id"] for case in SCENARIOS] == list(range(101, 110))
    assert {case["name"].removeprefix("refactoring-") for case in SCENARIOS} == runner.REQUIRED_SCENARIOS
    assert all(case["expectations"] and case["expected_output"] for case in SCENARIOS)


@pytest.fixture(scope="module", params=VARIANTS)
def runtime_copy(request, tmp_path_factory, frozen_inputs):
    # Real copying is needed to catch omitted resources and leaked development
    # files. Package selection depends on the variant, not the scenario prompt:
    # exercise that boundary once per variant, then check all prompts in memory.
    variant = request.param
    frozen, roots, records, before = frozen_inputs
    workspace = runner.make_workspace(tmp_path_factory.mktemp("runtime-copy"), variant)
    scenario = SCENARIOS[0]
    fixture = {"files": {"request.md": scenario["prompt"]}}
    manifest = runner.prepare_fixture(workspace, fixture, roots, roots["candidate"], variant)
    files = file_bytes(workspace)
    assert set(manifest["required_files"]) == set(files)
    assert files["request.md"] == scenario["prompt"].encode("utf-8")

    installed = workspace / ".agents/skills"
    packages = {"sdd-shared": roots["sdd-shared"], "humanizer-ru": roots["humanizer-ru"]}
    if variant != "without_skill":
        packages["sdd-spec"] = roots["old_skill" if variant == "old_skill" else "candidate"]
    assert {path.name for path in installed.iterdir()} == set(packages)
    for name, source in packages.items():
        copied = file_bytes(installed / name)
        source_bytes = file_bytes(source)
        assert copied["SKILL.md"] == source_bytes["SKILL.md"]
        for relative, content in copied.items():
            assert content == source_bytes[relative]
            assert relative.split("/")[0] not in {"tests", "evals", "eval-viewer"}
            assert relative not in {"agents/grader.md", "agents/analyzer.md",
                                    "agents/comparator.md", "agents/bineval.md"}
        # Hidden resources are runtime inputs too, not a blanket exclusion.
        for relative in source_bytes:
            if any(part.startswith(".") for part in Path(relative).parts) and not relative.startswith(("tests/", "evals/", "eval-viewer/")):
                assert copied[relative] == source_bytes[relative]
    for relative in ("scripts/check.py", "scripts/check.py.lock", "scripts/snapshot.py",
                     "scripts/snapshot.py.lock", "scripts/resolve_agent.py",
                     "scripts/resolve_agent.py.lock", "references/runtime-setup.md"):
        assert (installed / "sdd-shared" / relative).read_bytes() == (roots["sdd-shared"] / relative).read_bytes()
    assert (installed / "humanizer-ru/references/patterns.md").read_bytes() == (roots["humanizer-ru"] / "references/patterns.md").read_bytes()
    if variant == "without_skill":
        assert manifest["expected_missing_files"] == [".agents/skills/sdd-spec/SKILL.md"]
        assert not (installed / "sdd-spec").exists()
    else:
        assert manifest["expected_missing_files"] == []
        assert (installed / "sdd-spec/references/reviewer-plan.md").is_file()
        assert (installed / "sdd-spec/.gitignore").read_bytes() == (SKILL / ".gitignore").read_bytes()
    assert file_bytes(frozen) == before
    for name, record in records.items():
        assert runner.verify_package(record) == roots[name]
    assert "evals/evals.json" in records["old_skill"]["files"]
    assert "tests/test_refactoring_runner.py" in records["old_skill"]["files"]
    yield variant, files
    # Shared observations are read-only. Detect accidental fixture pollution
    # without re-reading the same files after every scenario.
    assert file_bytes(workspace) == files
    assert file_bytes(frozen) == before


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda case: str(case["id"]))
def test_refactoring_runtime_isolation_actual_oracles_are_not_executor_inputs(
        runtime_copy, scenario):
    variant, copied = runtime_copy
    files = {**copied, "request.md": scenario["prompt"].encode("utf-8")}
    # Inspect every oracle, not just this prompt or the training subset. Escaped
    # JSON strings count as leaks too. Prompts are inputs, never grading answers.
    for case in SCENARIOS:
        for answer in [case["expected_output"], *case["expectations"]]:
            representations = (answer.encode("utf-8"),
                               json.dumps(answer, ensure_ascii=True)[1:-1].encode("ascii"))
            for relative, content in files.items():
                assert all(value not in content for value in representations), (case["id"], variant, relative)


@pytest.mark.parametrize("variant", VARIANTS)
def test_refactoring_runtime_isolation_missing_required_resource_stops_preparation(
        tmp_path, frozen_inputs, monkeypatch, variant):
    frozen, roots, _, before = frozen_inputs
    copytree = runner.shutil.copytree

    def lose_resource(source, target, *args, **kwargs):
        result = copytree(source, target, *args, **kwargs)
        if Path(target).name == "sdd-shared":
            (Path(target) / "scripts/check.py.lock").unlink()
        return result

    monkeypatch.setattr(runner.shutil, "copytree", lose_resource)
    workspace = runner.make_workspace(tmp_path, variant)
    with pytest.raises(ValueError, match="Runtime package bytes or membership changed"):
        runner.prepare_fixture(workspace, {"files": {}}, roots, roots["candidate"], variant)
    assert file_bytes(frozen) == before
