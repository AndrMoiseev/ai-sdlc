"""Exercise installed consumers and the shared dependency without sdd-spec."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT.parent


def bootstrap(root=COLLECTION / 'sdd-spec'):
    spec = importlib.util.spec_from_file_location('bootstrap_probe', root / 'scripts/shared.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(script, *args, cwd=None, env=None):
    return subprocess.run(['uv', 'run', '--quiet', '--locked', '--script', str(script), *map(str, args)],
                          cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)


def install(tmp_path, consumers=()):
    collection = tmp_path / 'installed skills'
    for name in ('sdd-shared', *consumers):
        shutil.copytree(COLLECTION / name, collection / name)
    return collection


def inventory(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_bootstraps_are_identical_and_resolve_api():
    copies = [(COLLECTION / name / 'scripts/shared.py').read_bytes()
              for name in ('sdd-spec', 'sdd-setup')]
    assert copies[0] == copies[1]
    loader = bootstrap()
    assert loader.locate() == ROOT.resolve()
    assert loader.load(ROOT, 'subagents').ROLES
    with pytest.raises(ValueError, match='Unknown SDD shared module'):
        loader.load(ROOT, 'private')


@pytest.mark.parametrize('version', [0, 1, True, '2', None])
def test_api_version_is_checked_before_import(tmp_path, version):
    (tmp_path / 'api.json').write_text(json.dumps({'api_version': version}))
    with pytest.raises(ValueError, match='Incompatible sdd-shared API'):
        bootstrap().locate(explicit=tmp_path)


def test_incomplete_explicit_dependency_does_not_fall_back(tmp_path):
    (tmp_path / 'api.json').write_text(json.dumps({
        'api_version': 2, 'document_schemas': {
            'change': {kind: [2] for kind in ('state', 'review', 'decisions')}}}))
    with pytest.raises(ValueError, match='Incomplete sdd-shared'):
        bootstrap().locate(explicit=tmp_path)
    with pytest.raises(ValueError, match='not both'):
        bootstrap().locate(explicit=ROOT, legacy=COLLECTION / 'sdd-spec')


def test_settings_schema_roles_match_runtime():
    schema = json.loads((ROOT / 'schemas/settings.schema.json').read_text())
    roles = schema['properties']['subagents']['properties']['roles']['propertyNames']['enum']
    assert set(roles) == set(bootstrap().load(ROOT, 'subagents').ROLES)
    example = json.loads((ROOT / 'templates/settings.example.json').read_text())
    assert example['subagents']['roles']['sdd-spec.explorer'] == 'sdd-explorer'
    assert example['subagents']['roles']['sdd-apply.explorer'] == 'sdd-explorer'


@pytest.mark.parametrize('role', ['sdd-spec.explorer', 'sdd-apply.explorer'])
def test_explorer_resolver_preserves_lookup_fallback_and_errors(monkeypatch, role):
    resolver = bootstrap().load(ROOT, 'subagents')
    project = ROOT.resolve()
    user = project / 'memory-user-agents'
    settings_path = project / '.sdd/settings.json'
    files = {}

    def read_bytes(path):
        if path not in files:
            raise FileNotFoundError(path)
        return files[path]

    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(Path, 'iterdir', lambda path: iter(p for p in files if p.parent == path))

    def resolve():
        return resolver.resolve(project, role, 'codex', 'parent-model', 'high', user_agent_dir=user)

    expected = {'fork_turns': 'none', 'model': 'parent-model', 'reasoning_effort': 'high'}
    assert resolve()['reason'] == 'settings_missing'
    assert resolve()['launch'] == expected
    files[settings_path] = b'{"schema_version":1,"team":"preserved"}'
    assert resolve()['reason'] == 'role_unmapped'
    files[settings_path] = json.dumps({'schema_version': 1, 'team': 'preserved',
                                      'subagents': {'roles': {role: 'sdd-explorer'}}}).encode()
    assert resolve()['reason'] == 'agent_missing'
    assert resolve()['launch'] == expected
    definition = b'name="sdd-explorer"\ndescription="Explorer"\ndeveloper_instructions="role contract"\n'
    files[user / 'personal.toml'] = definition + b'model="user-model"\n'
    assert resolve()['launch'] == {'fork_turns': 'none', 'model': 'user-model'}
    project_agent = project / '.codex/agents/project.toml'
    files[project_agent] = definition
    before = files.copy()
    selection = resolve()
    assert selection['launch'] == expected
    assert selection['definition']['path'] == str(project_agent)
    assert selection['definition']['ignored_fields'] == ['developer_instructions']
    assert files == before
    files[project_agent.with_name('duplicate.toml')] = definition
    with pytest.raises(resolver.ConfigurationError, match='Duplicate agent name'):
        resolve()
    del files[project_agent.with_name('duplicate.toml')]
    files[project_agent] = b'not valid toml'
    with pytest.raises(resolver.ConfigurationError, match='Invalid agent TOML'):
        resolve()


@pytest.mark.parametrize('role', ['sdd-spec.explorer', 'sdd-apply.explorer'])
def test_explorer_claude_selection_uses_live_catalog(monkeypatch, role):
    resolver = bootstrap().load(ROOT, 'subagents')
    monkeypatch.setattr(resolver, 'settings', lambda project: ({role: 'sdd-explorer'}, None, 'role_unmapped'))
    selected = resolver.resolve(ROOT, role, 'claude-code', 'parent-model',
                                available_agents=['general-purpose', 'sdd-explorer'])
    assert selected['launch'] == {'subagent_type': 'sdd-explorer'}
    fallback = resolver.resolve(ROOT, role, 'claude-code', 'parent-model',
                                available_agents=['general-purpose'])
    assert fallback['reason'] == 'agent_missing'
    assert fallback['launch'] == {'subagent_type': 'general-purpose', 'model': 'parent-model'}
    with pytest.raises(resolver.ConfigurationError, match='No selected agent'):
        resolver.resolve(ROOT, role, 'claude-code', 'parent-model', available_agents=[])


def test_setup_runs_without_spec_from_relocated_install(tmp_path):
    collection = install(tmp_path, ('sdd-setup',))
    consumer = tmp_path / 'unrelated project'
    consumer.mkdir()
    (consumer / 'pyproject.toml').write_text('[project]\nname="conflict"\nversion="0.0.0"\ndependencies=["nonexistent-sdd-package==0"]\n')
    before, packages = inventory(consumer), inventory(collection)
    for _ in range(2):
        result = invoke(collection / 'sdd-setup/scripts/setup.py', 'inspect', '--project-root', consumer,
                        '--host', 'codex', '--user-agent-dir', tmp_path / 'empty-agents', cwd=consumer)
        assert result.returncode == 0, result.stderr + result.stdout
        inspection = json.loads(result.stdout)['result']
        assert len(inspection['roles']) == 10
        assert inspection['inputs']['sdd_shared'] == str((collection / 'sdd-shared').resolve())
    assert inventory(consumer) == before
    assert inventory(collection) == packages


@pytest.mark.parametrize('script,code,stream', [('check.py', 2, 'stdout'), ('snapshot.py', 2, 'stderr'), ('resolve_agent.py', 1, 'stdout')])
def test_legacy_command_missing_shared_reports_json(tmp_path, script, code, stream):
    package = tmp_path / 'sdd-spec'
    shutil.copytree(COLLECTION / 'sdd-spec', package)
    result = invoke(package / 'scripts' / script, '--project-root', tmp_path, '--change', 'demo', '--stage', 'plan')
    assert result.returncode == code
    report = json.loads(getattr(result, stream))
    assert 'sdd-shared' in str(report)
    assert 'Traceback' not in result.stderr


def test_shared_and_legacy_commands_have_identical_outputs(tmp_path):
    project = tmp_path / 'project'
    change = project / 'sdd/changes/sample-change'
    for name, relative in [('proposal', 'proposal.md'), ('design', 'design.md'), ('spec', 'specs/sample-capability/spec.md'), ('tasks', 'tasks.md')]:
        target = change / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((COLLECTION / 'sdd-spec/templates' / f'{name}.md').read_bytes())
    for script in ('check.py', 'snapshot.py'):
        for stage in ('documents', 'plan'):
            args = ['--project-root', project, '--change', 'sample-change', '--stage', stage]
            direct = invoke(ROOT / 'scripts' / script, *args)
            legacy = invoke(COLLECTION / 'sdd-spec/scripts' / script, *args)
            assert (direct.returncode, direct.stdout, direct.stderr) == (legacy.returncode, legacy.stdout, legacy.stderr)


def test_package_contains_only_sources_and_locks():
    for path in ROOT.rglob('*'):
        assert path.name not in {'.venv', '__pycache__', '.pytest_cache', 'node_modules'}
        assert path.suffix != '.pyc'
    for path in (ROOT / 'scripts').glob('*.py'):
        source = path.read_text()
        assert '# /// script' in source and 'sys.dont_write_bytecode = True' in source
        assert path.with_suffix('.py.lock').is_file()


def test_shared_links_resolve_in_declared_collection():
    for path in ROOT.rglob('*.md'):
        source = re.sub(r'(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$', '', path.read_text(encoding='utf-8'))
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', source):
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            result = (path.parent / target.split('#')[0]).resolve()
            assert result.is_relative_to(COLLECTION.resolve()) and result.is_file(), (path, target)


def test_fresh_cached_offline_and_stale_lock(tmp_path):
    collection = install(tmp_path)
    package = collection / 'sdd-shared'
    consumer = tmp_path / 'consumer'
    consumer.mkdir()
    env = dict(os.environ, UV_CACHE_DIR=str(tmp_path / 'external-cache'))
    before = inventory(package)
    script = package / 'scripts/check.py'
    failed = subprocess.run(['uv', 'run', '--locked', '--offline', '--script', str(script), '--help'], env=env, capture_output=True, timeout=60)
    assert failed.returncode != 0 and (b'offline' in failed.stderr.lower() or b'network' in failed.stderr.lower())
    for source in (ROOT / 'scripts/check.py', script, script):
        result = invoke(source, '--project-root', consumer, '--change', 'missing', '--stage', 'plan', cwd=consumer, env=env)
        assert result.returncode == 2, result.stderr + result.stdout
        assert json.loads(result.stdout)['errors'][0]['code'] != 'environment'
    assert inventory(package) == before and inventory(consumer) == {}
    script.write_text(script.read_text().replace('>=3.11', '>=3.11.1'))
    stale = invoke(script, '--help', cwd=consumer, env=env)
    assert stale.returncode != 0 and 'lock' in stale.stderr.lower()
    assert script.with_suffix('.py.lock').read_bytes() == before[Path('scripts/check.py.lock')]


@pytest.mark.parametrize("kind", ["deterministic", "manual", "behavioral"])
def test_execution_kind_public_contract_and_schema(kind):
    module = bootstrap().load(ROOT, "check_kinds")
    assert module.execution_kind({"run": {"command": ["python", "check.py"]}}) == "deterministic"
    assert module.execution_kind({"run": {"procedure": "checks.md"}, "execution_kind": kind}) == kind
    assert module.execution_kind({"run": {"command": ["agent", "evaluate"]}, "execution_kind": kind}) == kind
    with pytest.raises(ValueError, match="explicit type"):
        module.execution_kind({"run": {"procedure": "deterministic-looking-name.md"}})
    with pytest.raises(ValueError):
        module.execution_kind({"run": {"command": ["python"]}, "execution_kind": "unknown"})
    schema = json.loads((ROOT / "schemas/refactoring.schema.json").read_text())
    for name in ("taskCheck", "verification"):
        assert set(schema["$defs"][name]["properties"]["execution_kind"]["enum"]) == module.KINDS
        assert {"$ref": "#/$defs/executionKind"} in schema["$defs"][name]["allOf"]
    assert schema["$defs"]["executionKind"]["then"] == {"required": ["execution_kind"]}