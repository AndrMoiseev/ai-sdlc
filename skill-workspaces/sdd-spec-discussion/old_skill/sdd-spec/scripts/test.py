# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0", "pytest==8.4.2"]
# ///
"""Run the bundled regression suite without a consuming project's environment."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True

import pytest


if __name__ == "__main__":
    tests = Path(__file__).resolve().parents[1] / "tests"
    raise SystemExit(pytest.main([str(tests), "-p", "no:cacheprovider", *sys.argv[1:]]))
