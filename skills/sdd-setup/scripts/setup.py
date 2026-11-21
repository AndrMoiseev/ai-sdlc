# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3", "ruamel.yaml==0.18.16"]
# ///
"""Audit project requirements; inspect, plan and apply SDD role settings. JSON in; JSON out."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from setup_core import apply_plan, inspect_project, make_plan, read_json
from setup_io import read_request, save_result
from project_audit import audit_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Read-only project requirements audit")
    audit.add_argument("--project-root", required=True)
    stack = audit.add_mutually_exclusive_group(required=True)
    stack.add_argument("--jvm", dest="java_version", nargs="?", const="", metavar="JDK",
                       help="Check the source-declared JDK. Omit its value if unresolved.")
    stack.add_argument("--no-jvm", dest="java_version", action="store_const", const=None,
                       help="The audited project does not target the JVM")
    audit.add_argument("--output", type=Path, help="Save the audit to a new external JSON file")
    typespec = commands.add_parser("typespec", help="Inspect local TypeSpec after mise tool setup")
    typespec.add_argument("--project-root", required=True, type=Path)
    typespec.add_argument("--package-dir", type=Path, help="Package or workspace directory relative to project root")
    typespec.add_argument("--output", type=Path, help="Save the inspection to a new external JSON file")
    collection = commands.add_parser("collection", help="Verify and save the project audit command")
    collection.add_argument("--project-root", required=True, type=Path)
    collection.add_argument("--request", required=True, type=Path)
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
        if command == "audit":
            result = audit_project(**args)
        elif command == "typespec":
            from typespec_audit import inspect_typespec
            result = inspect_typespec(**args)
        elif command == "collection":
            from setup_collection import configure_collection
            result = configure_collection(args["project_root"], read_json(args["request"]))
        elif command == "inspect":
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
