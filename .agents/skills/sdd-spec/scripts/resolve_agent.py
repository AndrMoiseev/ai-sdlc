# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read SDD role settings and print a launch selection with source evidence."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from lib.subagents import ROLES, read_json, resolve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--role", required=True, choices=ROLES)
    parser.add_argument("--host", required=True, choices=("codex", "claude-code"))
    parser.add_argument("--parent-model", required=True)
    parser.add_argument("--parent-effort")
    parser.add_argument("--user-agent-dir", type=Path)
    parser.add_argument("--available-agents", type=Path,
                        help="JSON array of names from the actual Claude Code host catalog")
    args = vars(parser.parse_args())
    try:
        if args["available_agents"] is not None:
            args["available_agents"] = read_json(args["available_agents"])
        result = resolve(**args)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"ok": False, "code": "subagent_configuration", "message": str(exc)},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
