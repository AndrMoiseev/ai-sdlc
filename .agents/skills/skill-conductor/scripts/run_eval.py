#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Evaluate implicit skill selection in fresh Codex or Claude Code sessions."""

import argparse
import json
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.harness import HARNESSES, HarnessError, resolve_harness, run_prompt, save_run, skill_was_used
from scripts.utils import ensure_implicit_allowed, parse_skill_md


def find_project_root() -> Path:
    """Compatibility helper; candidates are installed only in temporary fixtures."""
    return Path.cwd()


def run_single_query(query: str, skill_name: str, skill_description: str,
                     timeout: int, project_root: str, model: str | None = None,
                     harness: str = "auto", output_dir: str | None = None) -> dict:
    selected = resolve_harness(harness)
    marker = "SKILL_CONDUCTOR_PROBE_" + uuid.uuid4().hex
    # Description-only probes do not copy the caller's repository or full skill.
    # Behavioral evals use run_task.py and explicitly prepared fixtures instead.
    with tempfile.TemporaryDirectory(prefix="skill-conductor-probe-") as directory:
        workspace = Path(directory)
        skill_dir = workspace / (".agents" if selected == "codex" else ".claude") / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        header = f"---\nname: {json.dumps(skill_name)}\ndescription: {json.dumps(skill_description, ensure_ascii=False)}\n---\n"
        (skill_dir / "SKILL.md").write_text(
            header + f"\n# Discovery probe\n\nReply with `{marker}` and stop. This probe measures selection only.\n",
            encoding="utf-8")
        result = run_prompt(query, workspace, selected, model, timeout)
        if output_dir:
            save_run(result, Path(output_dir))
        return {"triggered": skill_was_used(result, skill_name, marker) if result.status == "completed" else None,
                "status": result.status, "error": result.error, "duration_ms": result.duration_ms,
                "usage": result.usage}


def run_eval(eval_set: list[dict], skill_name: str, description: str,
             num_workers: int, timeout: int, project_root: Path,
             runs_per_query: int = 1, trigger_threshold: float = 0.5,
             model: str | None = None, harness: str = "auto",
             output_dir: Path | None = None) -> dict:
    selected = resolve_harness(harness)
    if not eval_set or num_workers < 1 or runs_per_query < 1 or timeout <= 0 or not 0 < trigger_threshold <= 1:
        raise ValueError("Use a nonempty eval set, positive workers/runs/timeout and a threshold in (0, 1]")
    if output_dir is not None and Path(output_dir).exists() and any(Path(output_dir).iterdir()):
        raise ValueError("output-dir must be empty; use a new directory for each evaluation")
    if not skill_name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in skill_name):
        raise ValueError("skill_name must be kebab-case")
    for item in eval_set:
        if not isinstance(item.get("query"), str) or not isinstance(item.get("should_trigger"), bool):
            raise ValueError("Each query needs a string query and a boolean should_trigger")
    runs = [[] for _ in eval_set]
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        pending = {}
        for index, item in enumerate(eval_set):
            for repetition in range(runs_per_query):
                destination = str(output_dir / f"query-{index + 1}" / f"run-{repetition + 1}") if output_dir else None
                future = executor.submit(run_single_query, item["query"], skill_name, description,
                                         timeout, str(project_root), model, selected, destination)
                pending[future] = (index, repetition)
        for future in as_completed(pending):
            index, repetition = pending[future]
            try:
                outcome = future.result()
            except Exception as exc:
                outcome = {"triggered": None, "status": "error", "error": str(exc),
                           "duration_ms": None, "usage": None}
            runs[index].append({"run": repetition + 1, **outcome})
    results = []
    for item, outcomes in zip(eval_set, runs):
        outcomes.sort(key=lambda run: run["run"])
        errors = [run["error"] for run in outcomes if run["status"] != "completed"]
        triggers = sum(run["triggered"] is True for run in outcomes)
        rate = triggers / len(outcomes) if not errors else None
        passed = not errors and (rate >= trigger_threshold if item["should_trigger"] else rate < trigger_threshold)
        results.append({"query": item["query"], "should_trigger": item["should_trigger"],
                        "trigger_rate": rate, "triggers": triggers, "runs": len(outcomes),
                        "pass": bool(passed), "errors": errors, "run_results": outcomes})
    passed = sum(item["pass"] for item in results)
    return {"skill_name": skill_name, "description": description, "harness": selected,
            "model": model, "results": results,
            "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed,
                        "errors": sum(len(item["errors"]) for item in results)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-set", required=True, type=Path)
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--description", default=None)
    parser.add_argument("--harness", choices=HARNESSES, default="auto")
    parser.add_argument("--model", default=None, help="Selected CLI's configured model by default")
    parser.add_argument("--num-workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--runs-per-query", type=int, default=3)
    parser.add_argument("--trigger-threshold", type=float, default=0.5)
    parser.add_argument("--output-dir", type=Path, help="Save raw events and metadata for each run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        selected = resolve_harness(args.harness)
        ensure_implicit_allowed(args.skill_path, selected)
        name, original_description, _ = parse_skill_md(args.skill_path)
        output = run_eval(json.loads(args.eval_set.read_text(encoding="utf-8-sig")), name,
                          args.description if args.description is not None else original_description,
                          args.num_workers, args.timeout, find_project_root(), args.runs_per_query,
                          args.trigger_threshold, args.model, selected, args.output_dir)
        if args.verbose:
            print(f"Harness: {selected}; results: {output['summary']}", file=sys.stderr)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output["summary"]["failed"] else 0
    except (HarnessError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
