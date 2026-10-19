# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0"]
# ///
"""Compatibility entry point; implementation belongs to sdd-shared."""
import sys
sys.dont_write_bytecode = True
import runpy
import json
from shared import locate

if __name__ == "__main__":
    try:
        root = locate()
    except ValueError as exc:
        print(json.dumps({'code': 'environment', 'message': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
    sys.path.insert(0, str(root / "scripts"))
    runpy.run_path(str(root / "scripts" / "snapshot.py"), run_name="__main__")
