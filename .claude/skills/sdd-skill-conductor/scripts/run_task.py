#!/usr/bin/env python3
"""Run a prepared behavioral eval with the selected CLI and save evidence."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.harness import HARNESSES, HarnessError, run_prompt, save_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=HARNESSES, default="auto")
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path, help="Prepared isolated fixture directory")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default=None, help="Selected CLI's configured model by default")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--allow-writes", action="store_true", help="Permit fixture edits under normal host permissions")
    args = parser.parse_args()
    try:
        if args.output_dir.exists() and any(args.output_dir.iterdir()):
            raise ValueError("output-dir must be empty; use a new directory for each run")
        result = run_prompt(args.prompt_file.read_text(encoding="utf-8-sig"), args.workspace,
                            args.harness, args.model, args.timeout, args.allow_writes)
        save_run(result, args.output_dir)
        print(json.dumps({"status": result.status, "harness": result.harness,
                          "output_dir": str(args.output_dir), "error": result.error}, ensure_ascii=False))
        return 0 if result.status == "completed" else 1
    except (HarnessError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
