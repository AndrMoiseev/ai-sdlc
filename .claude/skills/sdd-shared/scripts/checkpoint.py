# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Inspect, accept, or create a reviewed Git checkpoint. Inputs are JSON files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from sdd_shared import checkpoints
from sdd_shared.checkpoint_git import GitError


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("inspect", "accept", "create"))
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--work-kind", required=True, choices=("change", "refactoring"))
    parser.add_argument("--change", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-accepted", help="Full OID, or the literal null for an absent ref")
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--reviewed-changes", type=Path)
    parser.add_argument("--instruction", type=Path)
    parser.add_argument("--message")
    parser.add_argument("--review-changes", action="store_true", help="Include an ephemeral reviewed_changes tree observation")
    args = parser.parse_args(argv)
    identity = (args.project_root, args.work_kind, args.change)
    try:
        if args.operation == "inspect":
            result = checkpoints.inspect(*identity)
            if args.review_changes and result["exit_code"] == 0 and result["status"] not in ("unborn_head", "git_operation_in_progress"):
                result["reviewed_changes"] = checkpoints.capture_changes(args.project_root)
        else:
            if not args.expected_head or args.expected_accepted is None:
                parser.error("write operations require --expected-head and --expected-accepted (OID or null)")
            expected = (args.expected_head, None if args.expected_accepted == "null" else args.expected_accepted)
            if args.operation == "accept":
                if not args.decision:
                    parser.error("accept requires --decision JSON file")
                result = checkpoints.accept(*identity, *expected, _json(args.decision))
            else:
                if not args.reviewed_changes or not args.instruction or not args.message:
                    parser.error("create requires --reviewed-changes, --instruction JSON files and --message")
                result = checkpoints.create(*identity, *expected, _json(args.reviewed_changes), _json(args.instruction), args.message)
    except (OSError, ValueError, GitError) as exc:
        result = checkpoints._result(args.operation, args.work_kind, args.change)
        checkpoints._fail(result, getattr(exc, "code", "input_error"), str(exc), 2)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
