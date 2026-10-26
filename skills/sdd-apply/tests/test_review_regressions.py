from lib.repository import repository
from repository_support import commit, ignore
from conftest import Driver
import pytest
from pathlib import Path
from copy import deepcopy

def accepted_worktree(basis, tmp_path):
    from pathlib import Path
    d = Driver(basis)
    wt = Path(d.send('worktree_create', {'workspace': str(tmp_path / 'trees')})['path'])
    d.start()
    (wt / 'result.txt').write_text('result')
    d.freeze()
    d.verify()
    d.review()
    d.send('transfer')
    d.send('integrate')
    d.send('candidate')
    d.role('integration-verifier', 'verifier')
    d.send('check_run', {'role_id': 'integration-verifier', 'stage': 'integration'})
    d.review('integration-reviewer')
    d.send('commit')
    d.send('accept')
    for name in ['verifier', 'integration-verifier']:
        d.send('role_result', {'role_id': name, 'result': 'finished', 'trace': 'synthetic'})
    return d, wt


@pytest.fixture(scope="session")
def cleanup_template(project_template, basis_template, repository_seeds, tmp_path_factory):
    from checkpoints import Checkpoint, preparation
    from conftest import copy_project
    from memory_repository import MemoryRepositories
    workspace = tmp_path_factory.mktemp("cleanup-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)
    basis = deepcopy(basis_template)
    basis.update(project_root=str(root), change_root=str(root / "sdd/changes/demo"))
    with preparation(backend) as states:
        driver, _ = accepted_worktree(basis, workspace)
        return Checkpoint(workspace, driver, backend, states)


@pytest.fixture
def cleanup_checkpoint(cleanup_template, repository_backend, state_backend):
    driver = cleanup_template.restore(repository_backend, state_backend)
    return driver, Path(driver.task["worktree"]["path"]), Path(driver.state["basis"]["project_root"])


def test_cleanup_preserves_unknown_ignored_user_data(cleanup_checkpoint):
    d, wt, project = cleanup_checkpoint
    ignore(project, '*.local')
    valuable = wt / 'user-data.local'
    valuable.write_text('untransferred user data')
    with pytest.raises(ValueError, match='ignored.*data'):
        d.send('worktree_remove')
    assert valuable.read_text() == 'untransferred user data'


@pytest.mark.parametrize('crash_point', ['after_git', 'before_state'])
def test_cleanup_crash_reconciles_removed_worktree(cleanup_checkpoint, monkeypatch, crash_point):
    """The repository mutation succeeds, but its response is lost before persistence."""
    from lib import state
    d, wt, project = cleanup_checkpoint
    before = d.state
    with monkeypatch.context() as patch:
        if crash_point == 'after_git':
            repo = repository(project)
            remove = repo.remove_worktree
            def crash_after_git(path):
                remove(path)
                raise OSError('injected crash after Git removal')
            patch.setattr(repo, 'remove_worktree', crash_after_git)
        else:
            def crash_before_state(path, data):
                raise OSError('injected crash before state replacement')
            patch.setattr(state, 'save', crash_before_state)
        with pytest.raises(OSError, match='injected crash'):
            d.send('worktree_remove')
    assert not wt.exists()
    assert d.state == before
    d.number -= 1
    assert d.send('worktree_remove') == {'removed': str(wt)}
    assert d.task['worktree']['removed'] is True
    assert d.state['revision'] == before['revision'] + 1
    assert repository(project).worktree(wt) is None

def test_failed_latest_run_blocks_acceptance(execution_checkpoint, monkeypatch):
    driver = execution_checkpoint("verified")
    from lib import verification
    original = verification.run_command
    def failure(*args):
        result = original(*args)
        result.update(outcome='failed', exit_code=1)
        return result
    monkeypatch.setattr(verification, 'run_command', failure)
    assert driver.verify()['outcome'] == 'failed'
    assert driver.task['last_check_failed']
    with pytest.raises(ValueError, match='Latest required'):
        driver.review()

def test_ownership_path_alias_rejected(basis, project):
    (project / 'check.py').write_text('assert 2 + 3 == 5\n# foreign user work\n')
    driver = Driver(basis)
    driver.worktree()
    driver.send('checks_register', {'inventory': {'instructions': [], 'ci': []}})
    driver.role('author', 'executor')
    with pytest.raises(ValueError, match='canonical'):
        driver.send('start', {'role_id': 'author', 'paths': ['./check.py']})

def test_final_checks_cannot_accept_uncommitted_implementation(execution_checkpoint):
    driver = execution_checkpoint("accepted")
    project = Path(driver.state["basis"]["project_root"])
    committed = repository(project).content('HEAD', 'result.txt')
    (project / 'result.txt').write_text('different uncommitted implementation')
    driver.role('final', 'final_verifier')
    with pytest.raises(ValueError, match='before verification|changed'):
        driver.send('check_run', {'role_id': 'final', 'stage': 'final'})
    assert repository(project).content('HEAD', 'result.txt') == committed
    assert committed.decode().splitlines() == ['verified result']

def test_lost_reviewer_successor_finishes_reserved_round(execution_checkpoint):
    import pytest
    driver = execution_checkpoint("reviewing")
    driver.send('resume', {'host_trace': 'synthetic', 'live_contexts': ['verifier']}, task_id=None)
    driver.send('role_register', {'role_id': 'replacement', 'kind': 'reviewer', 'context_id': 'replacement', 'fresh': True, 'host': 'codex', 'launch_ref': 'synthetic', 'capabilities': {'fresh_context': True}, 'successor_of': 'reviewer'})
    driver.send('resume', {'host_trace': 'synthetic', 'live_contexts': ['replacement', 'verifier'], 'resolutions': [{'reason': 'lost_role', 'task_id': 'TASK-one', 'successor': 'replacement', 'evidence': 'registered'}]}, task_id=None)
    with pytest.raises(ValueError, match='existing review'):
        driver.send('review_start', {'role_id': 'replacement'})
    result = driver.send('review_result', {'role_id': 'replacement', 'candidate': driver.task['candidate'], 'verdict': 'pass', 'findings': [], 'test_integrity': 'inspected', 'trace': 'synthetic'})
    assert result['status'] == 'integrating'
