# /// script
# requires-python = ">=3.11"
# dependencies = []
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
        print(json.dumps({'ok': False, 'code': 'subagent_configuration', 'message': str(exc)}))
        raise SystemExit(1)
    sys.path.insert(0, str(root / "scripts"))
    runpy.run_path(str(root / "scripts" / "resolve_agent.py"), run_name="__main__")
