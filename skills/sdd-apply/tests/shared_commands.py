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
from functools import wraps
from collections import OrderedDict

from lib.common import require
import shared as dependency


_entrypoints = {}
_parser_caches = {}
_modules = {}
_source_loader = dependency.__file__


def source_module(module_name, work_kind="change"):
    # Relocated/missing dependency contracts must exercise the real loader.
    if dependency.__file__ != _source_loader:
        return dependency.load(module_name, work_kind=work_kind)
    key = module_name, work_kind
    if key not in _modules:
        _modules[key] = dependency.load(module_name, work_kind=work_kind)
    return _modules[key]


def remember(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > 512:
        cache.popitem(last=False)


def reuse_parsers(module):
    """Cache successful pure parses by exact text; return independent values."""
    yaml_cache, document_cache = _parser_caches.setdefault(
        Path(module.__file__), (OrderedDict(), OrderedDict()))
    parser = getattr(module, "safe_yaml", None)
    if parser is not None and not getattr(parser, "test_parse_cache", False):
        @wraps(parser)
        def parse(text):
            if text not in yaml_cache:
                # Invalid input must raise this import's own exception class.
                remember(yaml_cache, text, parser(text))
            yaml_cache.move_to_end(text)
            return deepcopy(yaml_cache[text])
        parse.test_parse_cache = True
        module.safe_yaml = parse
    reader = getattr(module, "read_document", None)
    if reader is not None and not getattr(reader, "test_parse_cache", False):
        document_type = module.Document
        @wraps(reader)
        def read(path, work_kind="change"):
            path = Path(path)
            try:
                content = path.read_bytes()
            except OSError:
                return reader(path, work_kind)  # Preserve the parser's InputError.
            key = path, work_kind, path.resolve(), content
            if key not in document_cache:
                result = reader(path, work_kind)
                remember(document_cache, key, (result.meta, result.records))
            document_cache.move_to_end(key)
            meta, records = deepcopy(document_cache[key])
            return document_type(path, meta, records)
        read.test_parse_cache = True
        module.read_document = read
    return module


def spec_modules(module_name="documents"):
    # This adapter uses the immutable source installation. Distribution tests
    # exercise locate/load directly against their separate copied packages.
    # Retain module objects, not parsed documents or validation outcomes.
    module = source_module(module_name)
    return reuse_parsers(module) if module_name == "documents" else module


def shared(name):
    return name == "sdd_shared" or name.startswith("sdd_shared.")


def entrypoint(dependency, script):
    """Reuse imports from a fixed fixture installation, never document results.

    A changed dependency belongs in a new fixture root, like a separate Python
    process. Reading every module on each CLI call does not improve isolation.
    """
    root = Path(dependency) / "scripts"
    key = str(root), script
    saved = _entrypoints.get(key)
    if saved is not None:
        sys.modules.update(saved[1])
        return saved[0]
    main = runpy.run_path(str(root / script))["main"]
    reuse_parsers(importlib.import_module("sdd_shared.documents"))
    modules = {name: module for name, module in sys.modules.copy().items() if shared(name)}
    for module in modules.values():
        reuse_parsers(module)
    _entrypoints[key] = main, modules
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
            from unittest.mock import patch
            from lib.repository import repository
            from lib.git_repository import GitRepository
            repo = repository(project)
            reviews = importlib.import_module("sdd_shared.reviews")
            if isinstance(repo, GitRepository):
                code = main(args)
            else:
                # Git checkpoint mechanics have their own native contract suite.
                # Keep real approval parsing here, with the existing repository adapter.
                def inspect(*args):
                    status = repo.status()
                    head = status["head"]
                    accepted = repo.accepted_checkpoint
                    return dict(schema_version=2, head=head, accepted_commit=accepted,
                                status="dirty" if status["dirty_paths"] else "ready" if head == accepted else "head_mismatch")
                class EvidenceGit:
                    def __init__(self, root): pass
                    def commit_exists(self, oid): return True
                with patch.object(reviews, "inspect", inspect), patch.object(reviews, "Git", EvidenceGit):
                    code = main(args)
            # Entry points import their domain modules inside main().
            loaded = {name: module for name, module in sys.modules.copy().items() if shared(name)}
            _entrypoints[str(Path(dependency) / "scripts"), script][1].update(loaded)
    finally:
        sys.path[:] = previous_path
        for name in tuple(sys.modules):
            if shared(name):
                del sys.modules[name]
        sys.modules.update(modules)
    require(code == 0, "sdd_check", stdout.getvalue() + stderr.getvalue())
    return json.loads(stdout.getvalue())
