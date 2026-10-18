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
        stage = sys.argv[sys.argv.index('--stage') + 1] if '--stage' in sys.argv and sys.argv.index('--stage') + 1 < len(sys.argv) else None
        print(json.dumps({'schema_version': 1, 'stage': stage,
                          'errors': [{'code': 'environment', 'path': '', 'element_id': None, 'message': str(exc)}],
                          'warnings': [], 'discussion_status': {'status': 'not_checked'},
                          'review_status': {'status': 'not_checked'}, 'approval_status': {'status': 'not_checked'}}))
        raise SystemExit(2)
    sys.path.insert(0, str(root / "scripts"))
    runpy.run_path(str(root / "scripts" / "check.py"), run_name="__main__")
