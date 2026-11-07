#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Full sequential deterministic suite; runtime state stays in the OS temp directory."""

import sys
sys.dont_write_bytecode = True

import unittest
from pathlib import Path

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1] / "tests"))
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(not result.wasSuccessful())
