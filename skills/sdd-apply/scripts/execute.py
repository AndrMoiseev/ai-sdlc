# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0"]
# ///
"""Execute deterministic SDD operations; all requests and responses are JSON."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--request", type=Path, help="JSON operation request")
    inputs.add_argument("--help-operation", nargs="?", const="", help="Read-only help for an operation (omit name to list all)")
    inputs.add_argument("--help-event", help="Read-only help for one event payload")
    args = parser.parse_args()
    try:
        from lib.api import dispatch
        if args.request is not None:
            request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        else:
            selector = ({"event": args.help_event} if args.help_event is not None else
                        {"operation": args.help_operation} if args.help_operation else {})
            request = {"operation": "help", "args": selector}
        result = dispatch(request)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_request"), "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
