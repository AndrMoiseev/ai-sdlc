#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Run a prepared behavioral eval with the selected CLI and save evidence."""

import argparse
import json
import sys
from pathlib import Path

# This launcher is also used directly from installed, read-only skill packages.
sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.harness import HARNESSES, HarnessError, run_prompt, save_run


def check_fixture(workspace: Path, manifest_path: Path) -> dict:
    """Check declared dependencies where the isolated executor will read them."""
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing fixture directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1):
        raise ValueError("fixture manifest must be an object with schema_version: 1")
    required = manifest.get("required_files")
    absent = manifest.get("expected_missing_files", [])
    for label, paths in (("required_files", required), ("expected_missing_files", absent)):
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p.strip() for p in paths):
            raise ValueError(f"{label} must be a list of nonempty relative file paths")
    checked, errors = [], []
    for paths, should_exist in ((required, True), (absent, False)):
        for name in paths:
            relative = Path(name)
            path = (workspace / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(workspace):
                errors.append(f"Path must stay inside the fixture: {name}")
                continue
            if should_exist:
                try:
                    with path.open("rb") as resource:
                        resource.read(1)
                except OSError as exc:
                    errors.append(f"Required fixture resource unavailable: {name}: {exc}")
                    continue
            elif path.exists():
                errors.append(f"Expected missing resource is present: {name}")
                continue
            checked.append({"path": name, "expected": "readable" if should_exist else "missing"})
    return {"status": "failed" if errors else "passed", "workspace": str(workspace),
            "manifest": str(manifest_path.resolve()), "checked": checked, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=HARNESSES, default="auto")
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path, help="Prepared isolated fixture directory")
    parser.add_argument("--fixture-manifest", required=True, type=Path,
                        help="JSON inventory of dependencies required inside this fixture")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight-only", action="store_true", help="Check fixture resources without starting a model")
    parser.add_argument("--model", default=None, help="Selected CLI's configured model by default")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--allow-writes", action="store_true", help="Permit fixture edits under normal host permissions")
    args = parser.parse_args()
    try:
        if args.output_dir.exists() and any(args.output_dir.iterdir()):
            raise ValueError("output-dir must be empty; use a new directory for each run")
        prompt = args.prompt_file.read_text(encoding="utf-8-sig")
        preflight = check_fixture(args.workspace, args.fixture_manifest)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "preflight.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8")
        if preflight["errors"]:
            print(json.dumps(preflight, ensure_ascii=False))
            return 1
        if args.preflight_only:
            print(json.dumps(preflight, ensure_ascii=False))
            return 0
        result = run_prompt(prompt, args.workspace,
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
