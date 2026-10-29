"""SDD shared API v2. Import only the domain module needed by the caller."""
from importlib import import_module

API_VERSION = 2
WORK_KINDS = frozenset({"change", "refactoring"})
MODULES = frozenset({"documents", "paths", "validation", "snapshots", "reviews", "subagents", "checkpoints", "explorer", "check_runner", "check_summary"})

def module(name):
    if name not in MODULES:
        raise ValueError(f"Unknown SDD shared module: {name}")
    return import_module("." + name, __name__)
