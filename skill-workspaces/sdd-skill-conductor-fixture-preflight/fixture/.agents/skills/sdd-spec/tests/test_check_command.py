"""Exercise the public process contract, not only the Python API."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SKILL = Path(__file__).resolve().parents[1]


def create_project(root):
    change = root / 'sdd/changes/sample-change'
    for kind, relative in [('proposal', 'proposal.md'), ('design', 'design.md'),
                           ('spec', 'specs/sample-capability/spec.md'), ('tasks', 'tasks.md')]:
        path = change / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((SKILL / 'templates' / f'{kind}.md').read_bytes())
    return change


def run_command(project, script='check.py', stage='documents', cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([sys.executable, str(SKILL / 'scripts' / script),
                           '--project-root', str(project), '--change', 'sample-change',
                           '--stage', stage], cwd=cwd or project, env=env,
                          capture_output=True, text=True, encoding='utf-8')


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('stage', ['documents', 'plan'])
def test_check_templates_from_other_directory(tmp_path, stage):
    project = tmp_path / 'project with spaces'
    change = create_project(project)
    before = hashes(project)
    result = run_command(project, stage=stage, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output['schema_version'] == 1
    assert output['stage'] == stage
    assert output['errors'] == []
    assert 'review_status' in output and 'approval_status' in output
    assert hashes(project) == before
    assert change.is_dir()


def test_documents_do_not_require_tasks(tmp_path):
    change = create_project(tmp_path)
    (change / 'tasks.md').unlink()
    result = run_command(tmp_path)
    assert result.returncode == 0, result.stdout
    assert run_command(tmp_path, stage='plan').returncode == 2


def test_structural_error_is_one_and_diagnostic(tmp_path):
    change = create_project(tmp_path)
    path = change / 'tasks.md'
    path.write_text(path.read_text(encoding='utf-8').replace('number: 1', 'number: 2'), encoding='utf-8')
    result = run_command(tmp_path, stage='plan')
    assert result.returncode == 1, result.stdout
    issue = json.loads(result.stdout)['errors'][0]
    assert {'code', 'path', 'element_id', 'message'} <= issue.keys()


@pytest.mark.parametrize('mode', ['missing', 'unsupported', 'invalid-utf8'])
def test_check_unperformed_is_two(tmp_path, mode):
    change = create_project(tmp_path)
    path = change / 'proposal.md'
    if mode == 'missing':
        path.unlink()
    elif mode == 'unsupported':
        path.write_text(path.read_text(encoding='utf-8').replace('schema_version: 1', 'schema_version: 99'), encoding='utf-8')
    else:
        path.write_bytes(b'\xff')
    result = run_command(tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads(result.stdout)['errors']


def test_snapshot_manifest_and_no_writes(tmp_path):
    change = create_project(tmp_path)
    before = hashes(tmp_path)
    result = run_command(tmp_path, script='snapshot.py', stage='plan')
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert [x['path'] for x in manifest] == sorted(x['path'] for x in manifest)
    assert {x['path'] for x in manifest} == {
        'proposal.md', 'design.md', 'tasks.md', 'specs/sample-capability/spec.md'}
    for entry in manifest:
        assert entry['sha256'] == hashlib.sha256((change / entry['path']).read_bytes()).hexdigest()
    assert hashes(tmp_path) == before


def test_snapshot_missing_input_has_json_diagnostic(tmp_path):
    create_project(tmp_path)
    (tmp_path / 'sdd/changes/sample-change/design.md').unlink()
    result = run_command(tmp_path, script='snapshot.py')
    assert result.returncode == 2
    assert json.loads(result.stderr)['code']
