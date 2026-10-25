# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3", "ruamel.yaml==0.18.16"]
# ///
"""Inspect, plan and apply project SDD settings. JSON in; JSON out."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from setup_core import apply_plan, inspect_project, make_plan, read_json
from setup_io import read_request, save_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--project-root", required=True)
    inspect.add_argument("--host", required=True, choices=("codex", "claude-code"))
    inspect.add_argument("--sdd-spec", help="Legacy sibling anchor for sdd-shared")
    inspect.add_argument("--sdd-shared")
    inspect.add_argument("--user-agent-dir")
    inspect.add_argument("--available-agents", type=Path)
    inspect.add_argument("--names", nargs="*", default=[])
    inspect.add_argument("--output", type=Path, help="Save full result to a new external JSON file; print review summary")
    plan = commands.add_parser("plan")
    plan.add_argument("--request", type=Path, required=True)
    plan.add_argument("--output", type=Path, help="Save full plan to a new external JSON file; print choices and exact diff")
    apply = commands.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    output = args.pop("output", None)
    try:
        if command == "inspect":
            if args["available_agents"] is not None:
                args["available_agents"] = read_json(args["available_agents"])
            result = inspect_project(**args)
        elif command == "plan":
            result = make_plan(read_request(args["request"]))
        else:
            result = apply_plan(read_json(args["plan"]))
        if output is not None:
            result = save_result(result, output, command)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "sdd_setup", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
