"""Migration keeps saved execution integrity and supports spec-free installs."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import pytest

from lib.common import write_json
from lib.inputs import basis_dependency
from lib.state import read, seal, save
from lib.subagents import resolve
from conftest import SPEC


def test_legacy_basis_resolution_preserves_saved_bytes(driver):
    state = driver.state
    state['basis'].pop('sdd_shared')
    state['basis']['sdd_spec'] = str(SPEC)
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


def test_new_basis_explicit_root_precedes_old_path(basis):
    mixed = deepcopy(basis)
    mixed['sdd_spec'] = '/missing/old-location'
    assert basis_dependency(mixed) == Path(basis['sdd_shared'])


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
    assert basis['checks']['plan']['approval_status']['ready']
    assert basis['sdd_shared'] == str((collection / 'sdd-shared').resolve())
    assert 'sdd_spec' not in basis

pytestmark = pytest.mark.native_state
