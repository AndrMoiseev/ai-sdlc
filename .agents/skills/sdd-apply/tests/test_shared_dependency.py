"""Only the sibling dependency is used, including when resuming old state."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest

from lib.common import write_json
from lib.api import dispatch
from lib.state import read, seal, save
from lib.subagents import resolve


def test_legacy_dependency_paths_are_ignored_without_rewriting(driver):
    state = driver.state
    state['basis']['sdd_shared'] = '/missing/old-shared'
    state['basis']['sdd_spec'] = '/missing/old-spec'
    seal(state)
    path = driver.directory / 'state.json'
    save(driver.directory, state)
    before = path.read_bytes()
    loaded = read(driver.directory)
    selection = resolve(loaded, 'executor', host='codex', parent_model='fixture-parent')
    assert selection['role'] == 'sdd-apply.executor'
    assert loaded == state and path.read_bytes() == before
    driver.send('resume', {'host_trace': 'unit-observation', 'live_contexts': []}, task_id=None)
    assert driver.state['basis'] == state['basis']


@pytest.mark.parametrize('selector', ['sdd_shared', 'sdd_spec'])
def test_dependency_path_arguments_are_rejected(basis, selector):
    assert 'sdd_shared' not in basis and 'sdd_spec' not in basis
    with pytest.raises(TypeError, match=selector):
        dispatch({'operation': 'validate', 'args': {
            'project_root': basis['project_root'], 'change': 'demo',
            'instruction': basis['instruction'], selector: '/unused/custom-path'}})


@pytest.mark.installation
def test_installed_apply_validates_without_spec(project, tmp_path):
    source = Path(__file__).resolve().parents[1]
    collection = tmp_path / 'installed skills'
    for name in ('sdd-apply', 'sdd-shared'):
        shutil.copytree(source.parent / name, collection / name)
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'operation': 'validate', 'args': {
        'project_root': str(project), 'change': 'demo',
        'instruction': {'text': 'Implement fixture', 'source': 'test'}}}))
    result = subprocess.run(['uv', 'run', '--locked', '--script', str(collection / 'sdd-apply/scripts/execute.py'), '--request', str(request)],
                            cwd=tmp_path, capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    basis = json.loads(result.stdout)['result']
    assert 'checks' not in basis
    assert 'sdd_shared' not in basis
    assert 'sdd_spec' not in basis

pytestmark = pytest.mark.native_state
