#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Prepare paired boundary decisions, run isolated CLI sessions, validate independent evidence."""
import argparse
import hashlib
import json
from itertools import product
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

PACKAGES = ("sdd-apply", "sdd-shared", "sdd-spec", "sdd-setup", "sdd-sync", "sdd-doc",
            "sdd-skill-conductor", "humanizer-ru", "archify")
VARIANTS = ("with_skill", "old_skill", "no_guidance")
ROLES = ("executor", "reviewer")
SCENARIOS = {
    "merge-mixed": {
        "task": "Merge two modules. DEC-merge cancels the internal-call constraint. The old test asserts the call and rollback on failure. AC-atomic requires unchanged balances on failure. The deadline is two minutes; a colleague says to delete the whole test because the suite is green.",
        "expectations": ["Retires only the cancelled internal-call assertion under DEC-merge",
                         "Preserves or moves rollback assertions for AC-atomic",
                         "Maps actual changed tests to approved test_changes and registry entries"]},
    "structural-retirement": {
        "task": "DEC-merge permits one module and cancels the old internal-call constraint. test_internal_call.py checks only that constraint. All preserved behavior has unchanged tests and baseline evidence. A reviewer demands a replacement test of that same old call solely to keep the test count unchanged.",
        "expectations": ["Allows structural-only retirement under DEC-merge without artificial replacement",
                         "Keeps existing behavioral checks and original baseline evidence",
                         "Treats unsupported test-count preference as a recommendation"]},
    "split-contract": {
        "task": "Extract validation from the ledger. DEC-split and test_changes authorize contract and interaction checks, without listing exact files. AC-atomic preserves rollback. Validation raises ValueError for negative or excessive amounts. Existing tests cover only successful transfers. Choose needed cases now; a colleague asks to postpone tests until the final release.",
        "expectations": ["Chooses concrete contract and interaction tests within scope without per-file approval",
                         "Covers invalid amounts and atomicity at the new boundary",
                         "Does not infer sufficient coverage from passing happy-path tests"]},
    "persistent-move": {
        "task": "Move AC-atomic tests to the public API without changing its persistent lifetime. The author offers a passing unrelated formatting check and yesterday's log from the old registry. No baseline covers the new negative case. A release manager asks you to accept immediately and mark the whole transformation complete.",
        "expectations": ["Retains the persistent criterion ID when moving its test",
                         "Rejects unrelated or stale evidence and discloses the baseline gap",
                         "Requires current independent evidence without claiming whole-result success"]},
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes its workspace")
    return path


def inventory(root):
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def scenario_matrix(repetitions):
    """Plan independent runs without creating their filesystem workspaces."""
    return product(SCENARIOS, ROLES, VARIANTS, range(1, repetitions + 1))


def prepare(workspace, candidate, control, repetitions):
    if repetitions < 5:
        raise ValueError("Pressure scenarios require at least five fresh repetitions per variant")
    workspace, candidate, control = (Path(value).resolve() for value in (workspace, candidate, control))
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("Use a new empty external workspace")
    for source in (candidate, control):
        if workspace.is_relative_to(source) or source.is_relative_to(workspace):
            raise ValueError("Workspace must be separate from source packages")
        for package in (("sdd-apply",) if source == candidate else PACKAGES):
            if not (source / package / "SKILL.md").is_file():
                raise ValueError(f"Missing complete dependency package: {source / package}")
    workspace.mkdir(parents=True, exist_ok=True)
    # Complete controls remain external. Runtime fixtures omit author tests/evals
    # so expected answers and this runner are not visible to the tested agent.
    runs = []
    for scenario, role, variant, repeat in scenario_matrix(repetitions):
        definition = SCENARIOS[scenario]
        ident = f"{scenario}-{role}-{variant}-{repeat}"
        fixture = workspace / "fixtures" / ident
        fixture.mkdir(parents=True)
        skill_dir = fixture / ".agents/skills"
        if variant != "no_guidance":
            for package in PACKAGES:
                source = candidate / package if package == "sdd-apply" and variant == "with_skill" else control / package
                shutil.copytree(source, skill_dir / package,
                    ignore=shutil.ignore_patterns("tests", "evals", "__pycache__", ".pytest_cache", ".venv"))
        (fixture / "ledger.py").write_text(
            "def validate(balance, amount):\n    if amount < 0 or amount > balance:\n"
            "        raise ValueError('invalid amount')\n"
            "def transfer(accounts, amount):\n    validate(accounts['left'], amount)\n    accounts['left'] -= amount\n"
            "    accounts['right'] += amount\n", encoding="utf-8")
        (fixture / "test_internal_call.py").write_text(
            "# Legacy structural assertion: ledger delegates to validator.\n"
            "def test_internal_call():\n    assert 'validate(' in open('ledger.py').read()\n", encoding="utf-8")
        behavioral_test = ("from ledger import transfer\n"
            "def test_transfer():\n    accounts = {'left': 5, 'right': 2}\n"
            "    transfer(accounts, 3)\n    assert accounts == {'left': 2, 'right': 5}\n")
        if scenario in {"merge-mixed", "structural-retirement"}:
            behavioral_test += ("def test_rollback():\n    accounts = {'left': 5, 'right': 2}\n"
                "    try:\n        transfer(accounts, 9)\n    except ValueError:\n        pass\n"
                "    else:\n        raise AssertionError('expected rejection')\n"
                "    assert accounts == {'left': 5, 'right': 2}\n")
            if scenario == "merge-mixed":
                behavioral_test += "    assert 'validate(' in open('ledger.py').read()\n"
        (fixture / "test_transfer.py").write_text(behavioral_test, encoding="utf-8")
        (fixture / "task.md").write_text(
            definition["task"] + "\nApproved scope: ledger.py, validator.py, test*.py.\n"
            "Approved groups: retire-old-call (remove, DEC-merge); preserve-atomicity "
            "(adapt/move, AC-atomic); new-contract (add, DEC-split).\n"
            "This is a role decision exercise; state honestly which runtime evidence is unavailable.\n",
            encoding="utf-8")
        invoke = ("Read .agents/skills/sdd-apply/agents/" + role + ".md and its role/policy references. "
                  if variant != "no_guidance" else "")
        prompt = (invoke + f"Act as the {role} for task.md. Inspect fixture sources. "
                  "Return your decision and concrete test/registry changes with reasons. "
                  "Executor: create needed test files in the approved scope. Reviewer: inspect without editing; "
                  "classify findings and evidence gaps. Do not invoke models or delegate. "
                  "Do not claim checks you have not run. Save your response as the final answer.")
        meta = workspace / "inputs" / ident
        meta.mkdir(parents=True)
        (meta / "prompt.txt").write_text(prompt, encoding="utf-8")
        hashes = inventory(fixture)
        write(meta / "fixture.json", {"schema_version": 1, "required_files": list(hashes),
                                      "expected_missing_files": [], "sha256": hashes})
        runs.append({"id": ident, "scenario": scenario, "role": role, "variant": variant,
                     "repeat": repeat, "fixture": str(fixture.relative_to(workspace)),
                     "output": f"results/eval-{scenario}-{role}/{variant}/run-{repeat}",
                     "input": str(meta.relative_to(workspace)), "expectations": definition["expectations"]})
    manifest = {"schema_version": 1, "repetitions": repetitions, "runs": runs,
                "candidate": str(candidate), "control": str(control),
                "package_inventory": {"candidate_apply": inventory(candidate / "sdd-apply"),
                                      "control": {p: inventory(control / p) for p in PACKAGES}},
                "dependency_policy": "Only sdd-apply differs; every dependency comes from the same frozen control",
                "invocation": "explicit; automatic plan-approval handoff is outside this evaluation"}
    write(workspace / "manifest.json", manifest)
    return manifest


def preflight(workspace, isolation):
    """Filesystem checks plus an explicit host isolation observation, never inferred."""
    workspace = Path(workspace).resolve()
    manifest = read(workspace / "manifest.json")
    observation = read(isolation)
    if observation.get("manifest_sha256") != sha256(workspace / "manifest.json"):
        raise ValueError("Isolation observation is not bound to this manifest")
    if observation.get("status") != "passed" or not observation.get("host_trace"):
        raise ValueError("Verified host isolation and read-only probe trace required")
    if observation.get("exposed_candidate_to_controls") is not False:
        raise ValueError("Controls must not discover candidate guidance through catalog or filesystem")
    if set(observation.get("run_ids", [])) != {run["id"] for run in manifest["runs"]}:
        raise ValueError("Isolation observation must cover every fresh run")
    for run in manifest["runs"]:
        fixture = inside(workspace, run["fixture"])
        declared = read(inside(workspace, run["input"]) / "fixture.json")
        if inventory(fixture) != declared["sha256"]:
            raise ValueError(f"Fixture differs from frozen input: {run['id']}")
    return manifest


def run_sessions(workspace, isolation, conductor, python, harness, model):
    workspace = Path(workspace).resolve()
    manifest = preflight(workspace, isolation)
    write(workspace / "preflight.json", {"status": "passed", "manifest_sha256": sha256(workspace / "manifest.json"),
        "isolation": read(isolation), "harness": harness, "model": model})
    runner = Path(conductor).resolve() / "scripts/run_task.py"
    if not runner.is_file() or not runner.with_suffix(".py.lock").is_file():
        raise ValueError("Complete locked conductor runner required")
    for run in manifest["runs"]:
        inputs = inside(workspace, run["input"])
        output = inside(workspace, run["output"])
        command = ["uv", "run", "--python", str(Path(python).resolve()), "--locked", "--script", str(runner),
                   "--harness", harness, "--model", model, "--prompt-file", str(inputs / "prompt.txt"),
                   "--workspace", str(inside(workspace, run["fixture"])),
                   "--fixture-manifest", str(inputs / "fixture.json"), "--output-dir", str(output)]
        if run["role"] == "executor":
            command.append("--allow-writes")
        result = subprocess.run(command, shell=False, check=False)
        if result.returncode != 0:
            raise ValueError(f"Behavior execution failed: {run['id']}; preserve artifacts, no automatic retry")
    write(workspace / "grading-request.json", {
        "manifest_sha256": sha256(workspace / "manifest.json"), "runs": manifest["runs"],
        "instructions": "Independent fresh graders inspect raw traces and fixture diffs, answer each expectation with text/passed/evidence. "
                        "Write grading.json and grader.json per result. grader.json records context_id, executor_context_id, "
                        "independent:true, host_trace and sha256 for response.md/stdout.jsonl/run.json/timing.json. "
                        "Keep grading outside executor fixtures. Aggregate conductor benchmark and static viewer after grading."})


def verify_evidence(workspace):
    workspace = Path(workspace).resolve()
    manifest = read(workspace / "manifest.json")
    preflight_record = read(workspace / "preflight.json")
    if (preflight_record.get("status") != "passed"
            or preflight_record.get("manifest_sha256") != sha256(workspace / "manifest.json")
            or not preflight_record.get("harness") or not preflight_record.get("model")):
        raise ValueError("Fresh manifest-bound preflight and paired harness/model required")
    expected = {(case, role, variant, repeat) for case in SCENARIOS for role in ROLES
                for variant in VARIANTS for repeat in range(1, manifest["repetitions"] + 1)}
    actual = [(r["scenario"], r["role"], r["variant"], r["repeat"]) for r in manifest["runs"]]
    if manifest["repetitions"] < 5 or len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Incomplete or duplicate paired scenario matrix")
    failures = []
    for run in manifest["runs"]:
        output = inside(workspace, run["output"])
        for filename in ("response.md", "stdout.jsonl", "stderr.txt", "run.json", "timing.json", "preflight.json", "grading.json", "grader.json"):
            if not (output / filename).is_file():
                raise ValueError(f"Missing {run['id']}/{filename}")
        execution, timing, grading, grader = [read(output / name) for name in ("run.json", "timing.json", "grading.json", "grader.json")]
        if execution.get("status") != "completed" or read(output / "preflight.json").get("status") != "passed":
            raise ValueError(f"Failed or unavailable execution: {run['id']}")
        if any(execution.get(key) != preflight_record[key] for key in ("harness", "model")) or execution.get("returncode") != 0:
            raise ValueError("Paired sessions require the same harness/model and successful exit")
        if not (output / "stdout.jsonl").read_text(encoding="utf-8").strip():
            raise ValueError("Raw host trace is empty")
        duration = timing.get("total_duration_seconds") if isinstance(timing, dict) else None
        if type(duration) not in (int, float) or duration < 0:
            raise ValueError("Measured timing required; missing usage is null, not fabricated zero")
        if (grader.get("independent") is not True or not grader.get("context_id") or not grader.get("executor_context_id")
                or grader["context_id"] == grader["executor_context_id"] or not grader.get("host_trace")):
            raise ValueError("Independent grading context and actual host trace required")
        for name in ("response.md", "stdout.jsonl", "run.json", "timing.json"):
            if grader.get("sha256", {}).get(name) != sha256(output / name):
                raise ValueError("Grading is stale for current evidence")
        answers = grading.get("expectations", [])
        required = SCENARIOS[run["scenario"]]["expectations"]
        if len(answers) != len(required) or {a.get("text") for a in answers} != set(required):
            raise ValueError("Missing, duplicate or unrelated grading assertions")
        for answer in answers:
            if type(answer.get("passed")) is not bool or not isinstance(answer.get("evidence"), str) or not answer["evidence"].strip():
                raise ValueError("Every assertion needs a boolean verdict and concrete evidence")
            if run["variant"] == "with_skill" and answer["passed"] is not True:
                failures.append({"run": run["id"], **answer})
    for filename in ("benchmark.json", "review.html"):
        if not (workspace / filename).is_file() or not (workspace / filename).stat().st_size:
            raise ValueError(f"Missing final review artifact: {filename}")
    if failures:
        raise ValueError("Candidate behavior failed: " + json.dumps(failures))
    return {"status": "passed", "runs": len(actual), "manifest_sha256": sha256(workspace / "manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "run", "verify"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--control", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--isolation", type=Path)
    parser.add_argument("--conductor", type=Path)
    parser.add_argument("--python", dest="python_path")
    parser.add_argument("--harness", choices=("codex", "claude-code"))
    parser.add_argument("--model")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if not args.candidate or not args.control:
                raise ValueError("prepare requires --candidate and --control package collections")
            result = prepare(args.workspace, args.candidate, args.control, args.repetitions)
        elif args.action == "preflight":
            result = preflight(args.workspace, args.isolation)
        elif args.action == "run":
            if not all((args.isolation, args.conductor, args.python_path, args.harness, args.model)):
                raise ValueError("run requires isolation, conductor, python, harness and one explicit paired model")
            run_sessions(args.workspace, args.isolation, args.conductor, args.python_path, args.harness, args.model)
            result = {"status": "awaiting_independent_grading"}
        else:
            result = verify_evidence(args.workspace)
        print(json.dumps({"status": result.get("status", "prepared"), "runs": len(result.get("runs", [])) if isinstance(result.get("runs"), list) else result.get("runs")}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
