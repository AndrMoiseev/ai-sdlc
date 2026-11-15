#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Collect inputs, calculate views, and validate authored refactoring recommendations."""

import sys
sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

from analysis_policy import load_policy, validate_policy
from audit_configuration import validate_audit_configuration
from collection import collect, inventory, report_output
from measurements import resolve_reference
from recommendations import markdown, rank


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value, repository, *, replace=False):
    output = report_output(path, repository)
    if output.exists() and not replace:
        raise ValueError(f"Output already exists: {output}; choose a new name")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_audit_configuration(value, path, repository):
    validate_audit_configuration(value)
    output = report_output(path, repository)
    audits = Path(repository).resolve() / "memory/tech-debt/audits"
    if output.name != "collection-input.json" or len(output.relative_to(audits).parts) != 2:
        raise ValueError("Save audit configuration as collection-input.json inside its audit")
    if any((output.parent / name).exists() for name in ("collection.json", "metrics", "selections")):
        raise ValueError("Collection has started; retain its configuration and use a new audit for recollection")
    write_json(output, value, repository, replace=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sub = commands.add_parser("policy", help="Resolve numeric policy through the script; print JSON without writing files")
    basis = sub.add_mutually_exclusive_group(required=True)
    basis.add_argument("--defaults", action="store_true")
    basis.add_argument("--repository", type=Path)
    basis.add_argument("--collection", type=Path)
    sub.add_argument("--get", help="Optional dotted policy key")
    sub = commands.add_parser("configure", help="Validate and save this audit's project-relative input; never edit project settings")
    sub.add_argument("--repository", required=True, type=Path)
    sub.add_argument("--input", type=Path, help="External candidate JSON; reads stdin when omitted")
    sub.add_argument("--output", required=True, type=Path)
    sub = commands.add_parser("collect", help="Collect every catalog output under memory/tech-debt/audits/<date-time>/")
    sub.add_argument("--repository", required=True, type=Path)
    sub.add_argument("--config", required=True, type=Path)
    sub.add_argument("--output", required=True, type=Path)
    sub.add_argument("--java", type=Path, help="Runtime JDK launcher outside the audit configuration")
    sub.add_argument("--detekt-jar", type=Path, help="Runtime detekt CLI all.jar outside the audit configuration")
    sub.add_argument("--focused", action="store_true", help="Explicit focused analysis; does not calculate or publish project status")
    sub = commands.add_parser("status", help="Publish status.json and status.md after the full report and plan are finished")
    sub.add_argument("--repository", required=True, type=Path)
    sub.add_argument("--collection", required=True, type=Path)
    sub = commands.add_parser("rank", help="Check Markdown cards and rank their metadata for sdd-spec discussion")
    sub.add_argument("--repository", required=True, type=Path)
    sub.add_argument("--collection", required=True, type=Path)
    sub.add_argument("--recommendations", required=True, type=Path)
    sub.add_argument("--output", required=True, type=Path)
    sub.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "policy":
            if args.repository is not None and not args.repository.is_dir():
                raise ValueError(f"Repository not found: {args.repository}")
            value = (validate_policy(read_json(args.collection)["analysis_policy"], complete=True)
                     if args.collection else load_policy(args.repository))
            if args.get:
                for part in args.get.split("."):
                    if not isinstance(value, dict) or part not in value:
                        raise ValueError(f"Unknown policy key: {args.get}")
                    value = value[part]
            print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
        elif args.command == "configure":
            if not args.repository.is_dir():
                raise ValueError(f"Repository not found: {args.repository}")
            value = read_json(args.input) if args.input else json.loads(sys.stdin.read())
            write_audit_configuration(value, args.output, args.repository)
            print(json.dumps({"configuration": str(args.output)}))
        elif args.command == "collect":
            if args.config.resolve() != args.output.resolve() / "collection-input.json":
                raise ValueError("Use collection-input.json from the selected audit directory")
            value = collect(read_json(args.config), args.output, repository=args.repository,
                            full=not args.focused, java=args.java, detekt_jar=args.detekt_jar)
            print(json.dumps({"collection": str(args.output / "collection.json"),
                              "complete_outputs": sum(row["status"] == "complete" for row in value["outputs"].values()),
                              "unavailable_outputs": sum(row["status"] != "complete" for row in value["outputs"].values()),
                              "candidate_groups": value["selections"]["candidate-groups"]["records"],
                              "gaps": value["gaps"]}))
        elif args.command == "status":
            from project_status import publish_status
            destination = publish_status(args.collection, args.repository)
            print(json.dumps({"json": str(destination / "status.json"), "markdown": str(destination / "status.md")}))
        else:
            collection = read_json(args.collection)
            report_output(args.collection, args.repository)
            if collection.get("status") != "complete":
                raise ValueError("Collection has unfinished calculations; inspect its output outcomes")
            policy = validate_policy(collection["analysis_policy"], complete=True)
            sources = inventory(collection["parameters"], args.repository.resolve())
            card_root = args.recommendations.resolve().parent
            def read_card(path):
                card_path = (card_root / path).resolve()
                if not card_path.is_relative_to(card_root):
                    raise ValueError("Markdown card must stay inside its report directory")
                return card_path.read_text(encoding="utf-8-sig")
            value = rank(read_json(args.recommendations), sources,
                         lambda ref: resolve_reference(ref, collection, args.collection.parent), read_card, policy=policy)
            destination = report_output(args.output, args.repository)
            if destination.exists():
                raise ValueError("Output already exists")
            if args.markdown:
                destination = report_output(args.markdown, args.repository)
                if destination.exists():
                    raise ValueError("Markdown output already exists")
                if destination == args.output.resolve():
                    raise ValueError("JSON and Markdown outputs must be different files")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(markdown(value), encoding="utf-8")
            write_json(args.output, value, args.repository)
            print(json.dumps({"output": str(args.output), "gaps": len(value.get("gaps", []))}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"sdd-architect: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
