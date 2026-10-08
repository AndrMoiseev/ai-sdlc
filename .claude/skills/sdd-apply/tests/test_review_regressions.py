from lib.common import git
from conftest import Driver
import pytest

def accepted_worktree(basis, tmp_path):
    from pathlib import Path
    d = Driver(basis, parallel=True)
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


def test_cleanup_preserves_unknown_ignored_user_data(basis, project, tmp_path):
    d, wt = accepted_worktree(basis, tmp_path)
    with (project / '.git/info/exclude').open('a') as stream:
        stream.write('\n*.local\n')
    valuable = wt / 'user-data.local'
    valuable.write_text('untransferred user data')
    with pytest.raises(ValueError, match='ignored data'):
        d.send('worktree_remove')
    assert valuable.read_text() == 'untransferred user data'


@pytest.mark.parametrize('crash_point', ['after_git', 'before_state'])
def test_cleanup_crash_reconciles_removed_worktree(basis, project, tmp_path, monkeypatch, crash_point):
    """Synthetic crash injection; the Git removal itself runs against a real fixture."""
    from lib import state, worktrees
    d, wt = accepted_worktree(basis, tmp_path)
    before = d.state
    with monkeypatch.context() as patch:
        if crash_point == 'after_git':
            real_git = worktrees.git
            def crash_after_git(root, *args, **kwargs):
                result = real_git(root, *args, **kwargs)
                if args[:2] == ('worktree', 'remove'):
                    raise OSError('injected crash after Git removal')
                return result
            patch.setattr(worktrees, 'git', crash_after_git)
        else:
            real_write = state.write_json
            def crash_before_state(path, data):
                if path.name == 'state.json':
                    raise OSError('injected crash before state replacement')
                return real_write(path, data)
            patch.setattr(state, 'write_json', crash_before_state)
        with pytest.raises(OSError, match='injected crash'):
            d.send('worktree_remove')
    assert not wt.exists()
    assert d.state == before
    d.number -= 1
    assert d.send('worktree_remove') == {'removed': str(wt)}
    assert d.task['worktree']['removed'] is True
    assert d.state['revision'] == before['revision'] + 1
    assert str(wt).replace('\\', '/') not in git(project, 'worktree', 'list', '--porcelain').replace('\\', '/')

def test_failed_latest_run_blocks_acceptance(driver, project, monkeypatch):
    driver.start()
    (project / 'result.txt').write_text('result')
    driver.freeze()
    assert driver.verify()['outcome'] == 'passed'
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
    driver.send('checks_register', {'inventory': {'instructions': [], 'ci': []}})
    driver.role('author', 'executor')
    with pytest.raises(ValueError, match='canonical'):
        driver.send('start', {'role_id': 'author', 'paths': ['./check.py']})

def test_final_checks_cannot_accept_uncommitted_implementation(driver, project):
    driver.start()
    (project / 'result.txt').write_text('original')
    driver.freeze()
    driver.verify()
    driver.review()
    driver.send('commit')
    driver.send('accept')
    (project / 'result.txt').write_text('different uncommitted implementation')
    driver.role('final', 'final_verifier')
    assert driver.send('check_run', {'role_id': 'final', 'stage': 'final'})['outcome'] == 'passed'
    assert driver.send('finalize', {}, task_id=None)['result'] == 'partial'
    assert git(project, 'show', 'HEAD:result.txt') == 'original'

def test_lost_reviewer_successor_finishes_reserved_round(driver, project):
    import pytest
    driver.start()
    (project / 'result.txt').write_text('result')
    driver.freeze()
    driver.verify()
    driver.role('reviewer', 'reviewer')
    driver.send('review_start', {'role_id': 'reviewer'})
    driver.send('resume', {'host_trace': 'synthetic', 'live_contexts': ['verifier']}, task_id=None)
    driver.send('role_register', {'role_id': 'replacement', 'kind': 'reviewer', 'context_id': 'replacement', 'fresh': True, 'host': 'codex', 'launch_ref': 'synthetic', 'capabilities': {'fresh_context': True}, 'successor_of': 'reviewer'})
    driver.send('resume', {'host_trace': 'synthetic', 'live_contexts': ['replacement', 'verifier'], 'resolutions': [{'reason': 'lost_role', 'task_id': 'TASK-one', 'successor': 'replacement', 'evidence': 'registered'}]}, task_id=None)
    with pytest.raises(ValueError, match='existing review'):
        driver.send('review_start', {'role_id': 'replacement'})
    result = driver.send('review_result', {'role_id': 'replacement', 'candidate': driver.task['candidate'], 'verdict': 'pass', 'findings': [], 'test_integrity': 'inspected', 'trace': 'synthetic'})
    assert result['status'] == 'committing'

