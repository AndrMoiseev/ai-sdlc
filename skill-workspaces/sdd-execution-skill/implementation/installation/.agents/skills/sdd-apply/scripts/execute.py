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
    parser.add_argument("--request", required=True, type=Path, help="JSON operation request")
    args = parser.parse_args()
    try:
        from lib.api import dispatch
        result = dispatch(json.loads(args.request.read_text(encoding="utf-8-sig")))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_request"), "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
