#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml>=6.0"]
# ///
"""Improve a skill description using the selected harness and training results."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.harness import HarnessError, require_success, resolve_harness, run_prompt
from scripts.utils import ensure_implicit_allowed, parse_skill_md


def _training_attempt(attempt: dict) -> dict:
    """Whitelist training fields; arbitrary notes can contain held-out evidence."""
    return {
        "description": attempt["description"],
        "passed": attempt.get("train_passed", attempt.get("passed", 0)),
        "total": attempt.get("train_total", attempt.get("total", 0)),
        "results": [
            {key: row[key] for key in ("query", "should_trigger", "pass", "triggers", "runs")}
            for row in attempt.get("train_results", attempt.get("results", []))
        ],
    }


def _parse_description(text: str) -> str:
    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    return (match.group(1) if match else text).strip().strip('"')


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
    harness: str = "auto",
    timeout: int = 120,
) -> str:
    """Optimize against training evidence only, without an SDK or provider key."""
    backend = resolve_harness(harness)
    if eval_results["summary"].get("errors", 0) or any(
        row.get("errors") or row.get("error") for row in eval_results["results"]
    ):
        raise HarnessError("Cannot improve a description from failed infrastructure runs.")

    training = _training_attempt({
        "description": current_description,
        "passed": eval_results["summary"]["passed"],
        "total": eval_results["summary"]["total"],
        "results": eval_results["results"],
    })
    prompt = f"""Improve the description for the agent skill {skill_name!r}, evaluated in {backend}.
The harness exposes the skill name and description before the agent decides to read SKILL.md.
Write a description that helps select the skill for relevant requests and excludes adjacent tasks.

Current training evidence:
{json.dumps(training, ensure_ascii=False, indent=2)}

Previous training attempts:
{json.dumps([_training_attempt(h) for h in history], ensure_ascii=False, indent=2)}

Skill content:
<skill_content>
{skill_content}
</skill_content>

Generalize failures into categories of user intent; avoid enumerating individual test queries.
Describe what the skill does and when to use it, including natural phrasings without its canonical
term and relevant exclusions. Keep workflow steps in the skill body. Make the description distinctive
among other available skills. Try a different formulation if previous attempts failed.
Use at most 1024 characters and no angle brackets in the description itself.
Return only the description enclosed in <new_description> tags."""

    transcript = {"iteration": iteration, "harness": backend, "model": model, "calls": []}
    description = ""
    try:
        with tempfile.TemporaryDirectory(prefix="skill-description-") as directory:
            workspace = Path(directory)

            def request(actual_prompt: str) -> str:
                result = run_prompt(
                    prompt=actual_prompt, workspace=workspace, harness=backend,
                    model=model, timeout=timeout, allow_writes=False,
                )
                transcript["calls"].append({
                    "prompt": actual_prompt, "response": result.text,
                    "harness": result.harness, "model": result.model,
                    "status": result.status, "error": result.error,
                    "duration_ms": result.duration_ms,
                })
                return require_success(result)

            description = _parse_description(request(prompt))
            if len(description) > 1024:
                shorten_prompt = (
                    "Shorten this skill description to at most 1024 characters while preserving "
                    "its intent and trigger coverage. Return only <new_description> tags containing "
                    f"the revised text.\n\nDescription ({len(description)} characters):\n{description}"
                )
                description = _parse_description(request(shorten_prompt))

            if not description or len(description) > 1024 or re.search(r"[<>]", description):
                raise ValueError("Improvement returned an empty or invalid description (limit: 1024 characters, no angle brackets).")
            transcript["final_description"] = description
            return description
    except (HarnessError, ValueError) as exc:
        transcript["error"] = str(exc)
        raise
    finally:
        transcript["char_count"] = len(description)
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"improve_iter_{iteration if iteration is not None else 'unknown'}.json").write_text(
                json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8",
            )


def main():
    parser = argparse.ArgumentParser(description="Improve a skill description from training eval results")
    parser.add_argument("--eval-results", required=True, help="Training results JSON from run_eval.py")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--history", help="Previous attempts JSON; only training fields are used")
    parser.add_argument("--harness", choices=("auto", "codex", "claude-code"), default="auto")
    parser.add_argument("--model", help="Model override; default uses the selected CLI configuration")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per improvement request in seconds")
    parser.add_argument("--log-dir", type=Path, help="Save prompts, responses, harness, and timing")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()
    try:
        backend = resolve_harness(args.harness)
        skill_path = Path(args.skill_path)
        ensure_implicit_allowed(skill_path, backend)
        eval_results = json.loads(Path(args.eval_results).read_text(encoding="utf-8"))
        history = json.loads(Path(args.history).read_text(encoding="utf-8")) if args.history else []
        name, _, content = parse_skill_md(skill_path)
        current_description = eval_results["description"]
        if args.verbose:
            print(f"Harness: {backend}; current description: {current_description}", file=sys.stderr)
        new_description = improve_description(
            skill_name=name, skill_content=content, current_description=current_description,
            eval_results=eval_results, history=history, model=args.model, harness=backend,
            timeout=args.timeout, log_dir=args.log_dir,
        )
        output = {
            "harness": backend, "model": args.model, "description": new_description,
            "history": history + [{
                "description": current_description, **eval_results["summary"],
                "results": eval_results["results"],
            }],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (HarnessError, ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
