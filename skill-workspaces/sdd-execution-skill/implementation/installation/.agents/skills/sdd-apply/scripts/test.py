# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0", "pytest==8.4.2"]
# ///
"""Run package tests from any cwd, without writing caches into the package."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import tempfile
import pytest

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    args = [str(root / a) if a.startswith("tests/") else a for a in sys.argv[1:]]
    if not any(not a.startswith("-") for a in args):
        args.insert(0, str(root / "tests"))
    temporary = Path(tempfile.mkdtemp(prefix="sdd-apply-tests-")) / "runs"
    raise SystemExit(pytest.main(["-c", str(root / "tests/pytest.ini"), "-p", "no:cacheprovider", "--basetemp", str(temporary), *args]))
