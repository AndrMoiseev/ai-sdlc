from lib.common import git
from lib.commits import own_paths
import pytest

def test_cleanup_deletes_unknown_ignored_user_data(basis, project, tmp_path):
    from pathlib import Path
    from conftest import module
    d = module.Driver(basis, parallel=True)
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
    with (project / '.git/info/exclude').open('a') as stream:
        stream.write('\n*.local\n')
    valuable = wt / 'user-data.local'
    valuable.write_text('untransferred user data')
    assert d.send('worktree_remove')['removed'] == str(wt)
    assert not valuable.exists()

def test_failed_latest_run_can_be_accepted(driver, project, monkeypatch):
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

def test_ownership_path_alias_and_directory_bypass(basis, project):
    from conftest import module
    (project / 'check.py').write_text('assert 2 + 3 == 5\n# foreign user work\n')
    driver = module.Driver(basis)
    driver.send('checks_register', {'inventory': {'instructions': [], 'ci': []}})
    driver.role('author', 'executor')
    with pytest.raises(ValueError, match='canonical'):
        driver.send('start', {'role_id': 'author', 'paths': ['./check.py']})

def test_final_checks_can_validate_uncommitted_defect_fix(driver, project):
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

def test_lost_reviewer_cannot_finish_reserved_round(driver, project):
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
