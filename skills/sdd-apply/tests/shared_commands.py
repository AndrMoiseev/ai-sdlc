"""Run the real shared CLI in process for document/rule tests.

Installation tests still launch uv. This adapter replaces process startup only:
argument parsing, document validation, JSON and exit-code handling remain real.
"""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import importlib
import os
import runpy
import sys
from pathlib import Path
from copy import deepcopy
from functools import lru_cache, wraps

from lib.common import require


_entrypoints = {}


def reuse_parsers(module):
    """Cache successful pure parses by exact text; return independent values."""
    parser = getattr(module, "safe_yaml", None)
    if parser is not None and not getattr(parser, "test_parse_cache", False):
        cached = lru_cache(maxsize=256)(parser)
        @wraps(parser)
        def parse(text):
            return deepcopy(cached(text))
        parse.test_parse_cache = True
        module.safe_yaml = parse
    reader = getattr(module, "read_document", None)
    if reader is not None and not getattr(reader, "test_parse_cache", False):
        @lru_cache(maxsize=256)
        def document(path, work_kind, resolved, content):
            return reader(path, work_kind)
        @wraps(reader)
        def read(path, work_kind="change"):
            path = Path(path)
            try:
                content = path.read_bytes()
            except OSError:
                return reader(path, work_kind)  # Preserve the parser's InputError.
            return deepcopy(document(path, work_kind, path.resolve(), content))
        read.test_parse_cache = True
        module.read_document = read
    return module


def spec_modules(root, module_name="documents"):
    from shared import load, locate
    root = Path(root)
    module = load(root if (root / "api.json").is_file() else locate(legacy=root), module_name)
    return reuse_parsers(module) if module_name == "documents" else module


def shared(name):
    return name == "sdd_shared" or name.startswith("sdd_shared.")


def entrypoint(dependency, script):
    """Reuse imports for unchanged dependency code, never document results."""
    root = Path(dependency) / "scripts"
    signature = tuple((str(path), path.read_bytes())
                      for path in sorted(root.rglob("*.py")))
    key = str(root), script
    saved = _entrypoints.get(key)
    if saved is not None and saved[0] == signature:
        sys.modules.update(saved[2])
        return saved[1]
    main = runpy.run_path(str(root / script))["main"]
    reuse_parsers(importlib.import_module("sdd_shared.documents"))
    modules = {name: module for name, module in sys.modules.copy().items() if shared(name)}
    for module in modules.values():
        reuse_parsers(module)
    _entrypoints[key] = signature, main, modules
    return main


def spec_call(dependency, project, change, stage, script, work_kind="change"):
    args = ["--project-root", str(project), "--change", change, "--stage", stage]
    if work_kind != "change":
        args += ["--work-kind", work_kind]
    # A copied dependency must import its own modules, just like a fresh CLI.
    modules = {name: module for name, module in sys.modules.copy().items() if shared(name)}
    previous_path = sys.path[:]
    stdout, stderr = StringIO(newline=os.linesep), StringIO(newline=os.linesep)
    try:
        for name in modules:
            del sys.modules[name]
        sys.path.insert(0, str(dependency / "scripts"))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            main = entrypoint(dependency, script)
            code = main(args)
            # Entry points import their domain modules inside main().
            loaded = {name: module for name, module in sys.modules.copy().items() if shared(name)}
            _entrypoints[str(Path(dependency) / "scripts"), script][2].update(loaded)
    finally:
        sys.path[:] = previous_path
        for name in tuple(sys.modules):
            if shared(name):
                del sys.modules[name]
        sys.modules.update(modules)
    require(code == 0, "sdd_check", stdout.getvalue() + stderr.getvalue())
    return json.loads(stdout.getvalue())
