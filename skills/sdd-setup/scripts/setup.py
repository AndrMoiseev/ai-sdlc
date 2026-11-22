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
from project_audit import audit_project, audit_jvm_step
from setup_progress import STEPS, progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    steps = commands.add_parser("progress", help="Read, reset, or record successfully verified setup steps")
    steps.add_argument("--project-root", required=True, type=Path)
    steps.add_argument("--applicable", nargs="*", choices=STEPS, help="Steps in the current route")
    change = steps.add_mutually_exclusive_group()
    change.add_argument("--reset", nargs="+", choices=(*STEPS, "all"))
    change.add_argument("--complete", choices=STEPS, help="Record a step after its checks passed in all applicable scopes")
    change.add_argument("--failed", choices=STEPS, help="Stop on a failed check without recording completion")
    steps.add_argument("--project-changed", action="store_true", help="This verified step changed project files")
    steps.add_argument("--check-exit-code", dest="check_exit_codes", action="append", type=int, default=[],
                       help="Exit code of each executed project ktlint or detekt check; repeat for multiple commands")
    audit = commands.add_parser("audit", help="Read-only project requirements audit")
    audit.add_argument("--project-root", required=True)
    audit.add_argument("--build-root", help="JVM build directory relative to project root")
    stack = audit.add_mutually_exclusive_group(required=True)
    stack.add_argument("--jvm", dest="java_version", nargs="?", const="", metavar="JDK",
                       help="Check the source-declared JDK. Omit its value if unresolved.")
    stack.add_argument("--no-jvm", dest="java_version", action="store_const", const=None,
                       help="The audited project does not target the JVM")
    for dependency in ("junit", "archunit"):
        audit.add_argument("--" + dependency, action="append", default=[], nargs=2, metavar=("VERSION", "EVIDENCE"),
                           help=f"Observed {dependency} version or check status, and evidence; repeat per observation")
    for tool in ("ktlint", "detekt"):
        applicability = audit.add_mutually_exclusive_group(required=True)
        applicability.add_argument("--" + tool, action="append", nargs=3,
                                   metavar=("SCOPE", "STATUS", "EVIDENCE"),
                                   help=f"Record observed {tool} integration for each applicable module or build")
        applicability.add_argument("--no-" + tool, dest=tool, action="store_const", const=(),
                                   help=f"No module or build in scope requires {tool}")
    audit.add_argument("--output", type=Path, help="Save the audit to a new external JSON file")
    jvm = commands.add_parser("jvm-step", help="Check one JVM setup step without repeating a full project audit")
    jvm.add_argument("step", choices=("jdk", "gradle", "junit5", "jacoco", "archunit"))
    jvm.add_argument("--project-root", required=True, type=Path)
    jvm.add_argument("--build-root", type=Path)
    jvm.add_argument("--jdk", default="", help="Required project JDK for the jdk step")
    jvm.add_argument("--observation", action="append", default=[], nargs=2, metavar=("VERSION", "EVIDENCE"),
                     help="Dependency observation for junit5 or archunit; repeat per scope")
    for command in (audit, jvm):
        command.add_argument("--jacoco-module", dest="jacoco_modules", action="append", default=[], metavar="MODULE",
                             help="Repeat for every JVM module in the audited build inventory")
        command.add_argument("--jacoco", action="append", default=[], nargs=3, metavar=("MODULE", "STATUS", "EVIDENCE"),
                             help="Result of verifying the aggregate report and test inputs for one JVM module")
    typespec = commands.add_parser("typespec", help="Inspect local TypeSpec after mise tool setup")
    typespec.add_argument("--project-root", required=True, type=Path)
    typespec.add_argument("--package-dir", type=Path, help="Package or workspace directory relative to project root")
    typespec.add_argument("--output", type=Path, help="Save the inspection to a new external JSON file")
    detekt = commands.add_parser("detekt", help="Compare recommended settings for one detekt task")
    detekt.add_argument("--project-root", required=True, type=Path)
    detekt.add_argument("--version", required=True, help="Resolved analyzer version")
    detekt.add_argument("--defaults", required=True, type=Path, help="Analyzer JAR or its default YAML")
    detekt.add_argument("--config", action="append", type=Path, default=[], help="Repeat in detekt task order")
    detekt.add_argument("--standalone", action="store_true", help="Project YAML replaces built-in defaults")
    detekt.add_argument("--ktlint", action="store_true", help="The detekt ktlint wrapper is loaded")
    detekt.add_argument("--accept", action="append", default=[], metavar="KEY|all",
                        help="Include a selected difference in the proposed YAML edits; repeat for more")
    detekt.add_argument("--output", type=Path, help="Save the comparison to a new external JSON file")
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
        if command == "progress":
            result = progress(**args)
        elif command == "jvm-step":
            result = audit_jvm_step(**args)
        elif command == "audit":
            result = audit_project(**args)
        elif command == "typespec":
            from typespec_audit import inspect_typespec
            result = inspect_typespec(**args)
        elif command == "detekt":
            from detekt_audit import inspect_detekt
            result = inspect_detekt(**args)
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
