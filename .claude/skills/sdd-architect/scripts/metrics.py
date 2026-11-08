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

from analysis import analyze
from collection import collect, identity, report_output
from recommendations import markdown, rank


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value, repository):
    output = report_output(path, repository)
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new name")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("identity", "collect"):
        sub = commands.add_parser(command, help="Capture source identity" if command == "identity" else "Collect inputs under docs/reports/<report-name>/")
        sub.add_argument("--config", required=True, type=Path)
        if command == "collect":
            sub.add_argument("--output", required=True, type=Path)
    sub = commands.add_parser("analyze", help="Calculate reproducible measurement views and investigation signals")
    sub.add_argument("--snapshot", required=True, type=Path)
    sub.add_argument("--output", required=True, type=Path)
    sub = commands.add_parser("rank", help="Validate authored recommendation cards; preserve equal priorities")
    sub.add_argument("--snapshot", required=True, type=Path)
    sub.add_argument("--recommendations", required=True, type=Path)
    sub.add_argument("--output", required=True, type=Path)
    sub.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "identity":
            config = read_json(args.config)
            value = identity(config, Path(config["repository"]).resolve())
            print(json.dumps({key: value[key] for key in ("revision", "dirty", "source_state")}, indent=2))
        elif args.command == "collect":
            value = collect(read_json(args.config), args.output)
            print(json.dumps({"snapshot": str(args.output / "snapshot.json"), "artifacts": list(value["artifacts"]), "gaps": value["gaps"]}))
        else:
            snapshot = read_json(args.snapshot)
            if args.command == "analyze":
                value = analyze(snapshot, args.snapshot.parent)
            else:
                value = rank(read_json(args.recommendations), snapshot)
                if args.markdown:
                    destination = report_output(args.markdown, snapshot.get("repository"))
                    if destination.exists():
                        raise ValueError("Markdown output already exists")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(markdown(value), encoding="utf-8")
            write_json(args.output, value, snapshot.get("repository"))
            print(json.dumps({"output": str(args.output), "gaps": len(value.get("gaps", []))}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"sdd-architect: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
