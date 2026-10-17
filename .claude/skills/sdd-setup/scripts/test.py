# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3", "ruamel.yaml==0.18.16", "pytest==8.4.2"]
# ///
"""Run setup regressions with isolated uv dependencies."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import pytest

if __name__ == "__main__":
    tests = Path(__file__).resolve().parents[1] / "tests"
    raise SystemExit(pytest.main([str(tests), "-c", str(tests / "pytest.ini"),
                                 "-p", "no:cacheprovider", *sys.argv[1:]]))
