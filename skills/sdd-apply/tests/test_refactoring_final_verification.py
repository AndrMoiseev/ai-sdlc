"""Real reducer lifecycles and executable typed-ID checks; host roles are synthetic."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from conftest import Driver
from lib import artifact_storage as artifacts
from lib.common import Rejected
from lib.dashboard import projection, render
from lib.final_checks import evidence, applicable
from lib.repository import repository
from lib.state import read, seal, save
from lib.state_storage import storage
from lib.state_view import compact
from refactoring_fixtures import RegistryDriver, approved_basis
from repository_support import stage as stage_files, commit


CORE = """class ProductId:
    def __init__(self, value):
        if type(value) is not int or value < 1:
            raise ValueError('invalid product')
        self.value = value
def lookup(product):
    if not isinstance(product, ProductId):
        raise TypeError('ProductId required')
    return {'id': product.value, 'name': 'product'}
"""
ADAPTER = "def adapt(value):\n    return lookup(ProductId(value))\n"
RAW = "def fetch(value):\n    return adapt(value)\n"
TYPED = "def fetch(value):\n    return lookup(ProductId(value))\n"
LOADER = """from pathlib import Path
def load(name):
    context = {}
    exec(Path('core.py').read_text(), context)
    if Path('adapter.py').exists():
        exec(Path('adapter.py').read_text(), context)
    exec(Path(name).read_text(), context)
    return context
"""
API = LOADER + """for name in ('consumer_a.py', 'consumer_b.py'):
    consumer = load(name)
    assert consumer['fetch'](7) == {'id': 7, 'name': 'product'}
    for invalid in (0, -1, '7'):
        try:
            consumer['fetch'](invalid)
        except ValueError as error:
            assert str(error) == 'invalid product'
        else:
            raise AssertionError('invalid external product accepted')
"""
WHOLE = LOADER + """assert not Path('adapter.py').exists(), 'temporary adapter remains'
for name in ('consumer_a.py', 'consumer_b.py'):
    consumer = load(name)
    assert 'adapt' not in consumer, name + ' retains a temporary adapter bypass'
    observed = []
    original = consumer['lookup']
    def observe(product):
        assert isinstance(product, consumer['ProductId']), name + ' bypasses ProductId'
        observed.append(product.value)
        return original(product)
    consumer['lookup'] = observe
    assert consumer['fetch'](7) == {'id': 7, 'name': 'product'}
    assert observed == [7], name + ' bypasses the typed core'
"""


def typed_basis(project, whole_setup=True, defect=None, procedure=False):
    def configure(documents):
        task, local, whole = documents['tasks']
        task.update(scope=[dict(module='core', paths=['core.py', 'adapter.py', 'check_adapter.py'])],
                    verification=[dict(id='adapter', criteria=['AC-local'], test_description='Working temporary conversion',
                                       location='check_adapter.py', run={'setup_required': 'Create adapter check'}),
                                  dict(id='api', criteria=['AC-preserved'], test_description='External API values and errors',
                                       location='check_api.py', run={'command': [sys.executable, '-B', 'check_api.py']})],
                    test_changes=[])
        local.update(lifetime='transitional', until_task='TASK-three', replaced_by=['AC-removed'])
        second = deepcopy(task)
        second.update(id='TASK-two', number=2, depends_on=['TASK-one'],
                      scope=[dict(module='consumer-a', paths=['consumer_a.py', 'check_a.py'])],
                      verification=[dict(id='consumer-a', criteria=['AC-a'], test_description='Consumer A typed boundary',
                                         location='check_a.py', run={'setup_required': 'Create consumer A check'}), deepcopy(task['verification'][1])])
        third = deepcopy(task)
        third.update(id='TASK-three', number=3, depends_on=['TASK-two'],
                     scope=[dict(module='consumer-b', paths=['consumer_b.py', 'adapter.py', 'check_adapter.py', 'check_removed.py', 'check_whole.py'])],
                     verification=[dict(id='removed', criteria=['AC-removed'], test_description='Adapter removed; API works',
                                        location='check_removed.py', run={'setup_required': 'Check removed adapter'}), deepcopy(task['verification'][1])])
        local_a = dict(sdd_record='acceptance', id='AC-a', task='TASK-two', lifetime='persistent',
                       conditions='Consumer A is migrated', expected='Consumer A calls the typed core')
        removed = dict(sdd_record='acceptance', id='AC-removed', task='TASK-three', lifetime='persistent',
                       conditions='Migration has ended', expected='Temporary adapter is removed')
        whole.update(location='check_whole.py', run={'setup_required': 'Create complete consumer traversal'}, setup_task='TASK-three')
        if not whole_setup:
            whole.pop('setup_task')
            whole['run'] = {'command': [sys.executable, '-B', 'check_whole.py']}
        if procedure:
            whole.pop('setup_task', None)
            whole.update(location='whole-procedure.md', run={'procedure': 'whole-procedure.md'})
            (project / 'whole-procedure.md').write_text(
                'Run check_whole.py to traverse both consumers, check ProductId calls, adapter absence and API errors. '
                'Record the executed command and outcome; if interrupted or unavailable, report that outcome.\n', encoding='utf-8')
        documents['tasks'] = [task, local, second, local_a, third, removed, whole]
        for name, source in {'core.py': CORE, 'adapter.py': ADAPTER, 'consumer_a.py': RAW,
                             'consumer_b.py': RAW, 'check_api.py': API}.items():
            (project / name).write_text(source, encoding='utf-8')
    return approved_basis(project, configure=configure)


class FinalDriver(RegistryDriver):
    def implement(self, defect=None, setup=True):
        if self.task_id == 'TASK-one':
            name, ident = 'check_adapter.py', 'adapter'
            source = LOADER + "assert Path('adapter.py').is_file()\nassert load('consumer_a.py')['fetch'](7)['id'] == 7\n"
        elif self.task_id == 'TASK-two':
            (self.root / 'consumer_a.py').write_text(TYPED, encoding='utf-8')
            name, ident = 'check_a.py', 'consumer-a'
            source = LOADER + "consumer = load('consumer_a.py')\nconsumer['adapt'] = lambda value: (_ for _ in ()).throw(AssertionError('adapter used'))\nassert consumer['fetch'](7)['id'] == 7\n"
        else:
            consumer = TYPED
            if defect == 'missing-consumer':
                consumer = "def fetch(value):\n    if type(value) is not int or value < 1: raise ValueError('invalid product')\n    return {'id': value, 'name': 'product'}\n"
            if defect == 'adapter-bypass':
                consumer = ADAPTER + RAW
            (self.root / 'consumer_b.py').write_text(consumer, encoding='utf-8')
            (self.root / 'adapter.py').unlink()
            (self.root / 'check_adapter.py').unlink()
            name, ident = 'check_removed.py', 'removed'
            source = "from pathlib import Path\nassert not Path('adapter.py').exists()\n"
            (self.root / 'check_whole.py').write_text(WHOLE + "\n" + API, encoding='utf-8')
            if setup:
                self.send('check_setup', dict(check_id='CHECK-whole', command=[sys.executable, '-B', 'check_whole.py'],
                    description='Observe each consumer crossing the typed core and preserve exact external values/errors'), task_id=None)
        (self.root / name).write_text(source, encoding='utf-8')
        self.send('check_setup', dict(check_id=self.task_id + '/' + ident, command=[sys.executable, '-B', name],
                                     description='Executable local boundary assertion'))
        if self.task_id == 'TASK-three':
            from lib.check_registry import selected
            before = deepcopy(selected(self.state, self.task))
            after = [check for check in before if check['id'] != 'TASK-one/adapter']
            self.send('checks_revise', dict(registry_revision=self.task['check_registry']['revision'],
                before=before, after=after, basis={'transitional_criteria': ['AC-local']}, preserves=[],
                reason='Approved adapter removal at TASK-three', mapping={'TASK-one/adapter': 'AC-local ends at TASK-three; check_adapter.py removed; check_removed.py covers AC-removed'}))

    def finish(self):
        self.freeze()
        assert self.verify()['outcome'] == 'passed'
        self.review()
        self.integrate(prefix=self.task_id + '-')
        self.send('commit')
        assert self.send('accept')['status'] == 'accepted'

    def final_role(self, ident='final', context=None, successor_of=None):
        return self.send('role_register', dict(role_id=ident, kind='final_verifier', context_id=context or ident,
            fresh=True, host='codex', launch_ref='synthetic-unit-test', capabilities={'fresh_context': True},
            **({'successor_of': successor_of} if successor_of else {})), task_id=None)

    def run_final(self, role='final'):
        return self.send('check_run', {'role_id': role, 'stage': 'final'}, task_id=None)


def completed(project, parallel=False, defect=None, setup=True, procedure=False):
    driver = FinalDriver(typed_basis(project, procedure=procedure), parallel=parallel)
    driver.send('checks_register', {'inventory': {'instructions': [], 'ci': []}}, task_id=None)
    for task_id in ('TASK-one', 'TASK-two', 'TASK-three'):
        driver.task_id = task_id
        assert driver.start()['outcome'] == 'baseline_recorded'
        driver.implement(defect, setup=setup and not procedure)
        driver.finish()
    return driver


@pytest.mark.parametrize('parallel', [False, True])
def test_complete_typed_migration_with_independent_whole_result(project, parallel):
    driver = completed(project, parallel)
    driver.final_role()
    result = driver.run_final()
    assert result['outcome'] == 'passed'
    log = driver.log(result)
    assert log['task_id'] is None
    ids = {output['check_id'] for output in log['outputs']}
    assert 'TASK-one/adapter' not in ids
    assert {'CHECK-whole', 'TASK-one/api', 'TASK-two/api', 'TASK-three/api', 'TASK-two/consumer-a', 'TASK-three/removed'} <= ids
    final = driver.send('finalize', task_id=None)
    assert final['result'] == 'complete'
    assert set(final['accepted_criteria']) == {'AC-result', 'AC-preserved', 'AC-a', 'AC-removed'}
    assert final['retired_checks'][0]['check_id'] == 'TASK-one/adapter'
    assert final['retired_checks'][0]['reason'] == 'Approved adapter removal at TASK-three'
    assert final['basis']['source']['commit'] == repository(project).head()
    assert driver.state['roles']['final']['task_id'] is None
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == ['AC-preserved', 'AC-result']
    assert compact(driver.state)['whole_result']['total_criteria'] == 2


@pytest.mark.parametrize('defect', ['missing-consumer', 'adapter-bypass'])
def test_local_acceptance_does_not_prove_complete_migration(project, defect):
    driver = completed(project, defect=defect)
    # An inlined temporary adapter is an unauthorized bypass even if externally compatible.
    if defect == 'adapter-bypass':
        # The whole assertion inspects conversion at the boundary as well as actual calls.
        assert 'adapt' in (project / 'consumer_b.py').read_text()
    driver.final_role()
    result = driver.run_final()
    assert result['outcome'] == 'failed'
    assert result['failures'] == ['CHECK-whole']
    assert all(task['status'] == 'accepted' for task in driver.state['tasks'].values())
    final = driver.send('finalize', task_id=None)
    assert final['result'] == 'partial'
    assert 'AC-result' not in final['accepted_criteria']
    assert any(gap.get('check_id') == 'CHECK-whole' for gap in final['missing'])


def test_unprepared_whole_setup_fails_closed(project):
    driver = completed(project, setup=False)
    driver.final_role()
    result = driver.run_final()
    assert result['outcome'] == 'failed'
    assert next(output for output in driver.log(result)['outputs'] if output['check_id'] == 'CHECK-whole')['outcome'] == 'unavailable'
    assert driver.send('finalize', task_id=None)['result'] == 'partial'


@pytest.mark.parametrize('drift', ['head', 'manifest', 'registry'])
def test_final_evidence_is_bound_to_current_head_manifest_and_registry(project, drift):
    driver = completed(project)
    driver.final_role()
    assert driver.run_final()['outcome'] == 'passed'
    state = driver.state
    if drift == 'head':
        (project / 'new-code.txt').write_text('new integrated code\n')
        stage_files(project, 'new-code.txt')
        commit(project, 'Independent integrated change')
    elif drift == 'manifest':
        state['basis']['manifest'] = [*state['basis']['manifest'], {'path': 'new.md', 'sha256': 'different'}]
    else:
        state['final_checks']['revision'] += 1
        state['final_checks']['history'].append(dict(revision=state['final_checks']['revision'], event_id='new-registry', checks=deepcopy(state['final_checks']['checks'])))
    _, matches, gaps = evidence(state, driver.directory)
    assert matches == []
    assert gaps and all(gap['reason'] == 'final_evidence_missing' for gap in gaps)


def test_final_rejects_author_and_task_bound_final_context(project):
    driver = completed(project)
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.final_role(context='TASK-one-author')
    assert error.value.code == 'context_reused'
    assert storage(driver.directory).read() == before
    with pytest.raises(Rejected) as error:
        driver.role('task-final', 'final_verifier')
    assert error.value.code == 'final_role'
    assert storage(driver.directory).read() == before


def test_unrelated_success_and_changed_logs_cannot_prove_final_checks(project):
    driver = completed(project)
    driver.final_role()
    assert driver.run_final()['outcome'] == 'passed'
    state = driver.state
    item = state['final_checks']['evidence'][-1]
    import json
    from lib.common import digest
    path = driver.directory / item['log']
    log = json.loads(artifacts.read_text(path))
    log['outputs'][-1]['command'] = [sys.executable, '-B', '-c', 'pass']
    artifacts.write(path, json.dumps(log))
    for entry in state['final_checks']['evidence']:
        entry['log_hash'] = digest(artifacts.read_bytes(path))
    before = storage(driver.directory).read()
    before_log = artifacts.read_bytes(path)
    with pytest.raises(Rejected) as error:
        evidence(state, driver.directory)
    assert error.value.code == 'evidence_command'
    assert storage(driver.directory).read() == before
    assert artifacts.read_bytes(path) == before_log


def test_final_failure_requires_owned_budgeted_repair_before_retry(project):
    driver = completed(project, defect='missing-consumer')
    driver.final_role()
    assert driver.run_final()['outcome'] == 'failed'
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.run_final()
    assert error.value.code == 'repair_owner_required'
    assert storage(driver.directory).read() == before
    result = driver.send('repair', dict(reason='Consumer B bypasses core', defect_evidence='CHECK-whole trace: no typed call',
        final_checks=['CHECK-whole'], paths=['consumer_b.py']))
    assert result['status'] == 'repairing'
    assert driver.task['test_repair_cycles_started'] == 1
    assert driver.task['worktree'] is None
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.run_final()
    assert error.value.code == 'final_tasks'
    assert storage(driver.directory).read() == before


def test_unknown_final_repair_owner_returns_to_spec(project):
    driver = completed(project, defect='missing-consumer')
    driver.final_role()
    assert driver.run_final()['outcome'] == 'failed'
    result = driver.send('repair', dict(reason='Unplanned consumer', defect_evidence='Consumer outside all authorized task paths',
        final_checks=['CHECK-whole'], paths=['forgotten.py']), task_id=None)
    assert result['return_to'] == 'sdd-spec'
    assert driver.state['status'] == 'blocked'
    assert all(task['status'] == 'accepted' for task in driver.state['tasks'].values())


def test_post_integration_regression_invalidates_success_and_is_detected(project):
    driver = completed(project)
    driver.final_role()
    assert driver.run_final()['outcome'] == 'passed'
    (project / 'consumer_b.py').write_text(TYPED.replace('lookup(ProductId(value))', "{'id': value, 'name': 'wrong'}"))
    stage_files(project, 'consumer_b.py')
    commit(project, 'Integration regression')
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == []
    assert driver.run_final()['outcome'] == 'failed'
    assert 'TASK-one/api' in driver.state['final_checks']['failures']
    assert driver.send('finalize', task_id=None)['result'] == 'partial'


def test_dashboard_separates_tasks_criteria_gaps_and_retirement(project):
    driver = completed(project, defect='missing-consumer')
    driver.final_role()
    assert driver.run_final()['outcome'] == 'failed'
    data = projection(driver.state)
    assert data['accepted'] == data['total'] == 3
    assert data['whole_result']['confirmed_criteria'] == []
    assert data['whole_result']['gaps'][0]['check_id'] == 'CHECK-whole'
    render(driver.directory)
    html = artifacts.read_text(driver.directory / 'dashboard.html')
    summary = artifacts.read_text(driver.directory / 'summary.md')
    assert 'Whole result' in html and 'CHECK-whole' in html
    assert 'Retired checks and reasons' in summary and 'Approved adapter removal at TASK-three' in summary


def begin_procedure(driver, role='final'):
    return driver.send('procedure_begin', dict(check_id='CHECK-whole', role_id=role, stage='final'), task_id=None)


def finish_procedure(driver, role='final', outcome='passed'):
    # The fixture host executes the prescribed Python assertion file; the engine
    # receives the same public procedure attestation a real final verifier uses.
    from lib import verification
    output = verification.run_command([sys.executable, '-B', 'check_whole.py'], driver.root, 30)
    assert output['outcome'] == 'passed' and output['exit_code'] == 0
    return driver.send('procedure_result', dict(check_id='CHECK-whole', role_id=role, outcome=outcome,
        steps=[{'command_execution': output, 'host_observation': outcome}],
        trace='synthetic-unit-test procedure host: executed typed-ID traversal; final observation=' + outcome), task_id=None)


def procedure_pass(driver):
    driver.final_role()
    attempt = begin_procedure(driver)
    result = finish_procedure(driver)
    assert result['attempt_id'] == attempt['attempt_id']
    assert result['outcome'] == 'passed'
    aggregate = driver.run_final()
    assert aggregate['outcome'] == 'passed'
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == ['AC-preserved', 'AC-result']
    return result, aggregate


@pytest.mark.parametrize('outcome', ['pending', 'failed', 'unavailable', 'skipped', 'unstable'])
def test_newer_same_basis_procedure_supersedes_aggregate_pass(project, outcome):
    driver = completed(project, procedure=True)
    previous, aggregate = procedure_pass(driver)
    before_basis = deepcopy(previous['basis'])
    next_attempt = begin_procedure(driver)
    assert next_attempt['basis'] == before_basis
    assert next_attempt['attempt_id'] != previous['attempt_id']
    if outcome != 'pending':
        result = finish_procedure(driver, outcome=outcome)
        assert result['basis'] == before_basis and result['outcome'] == outcome
        assert driver.state['final_checks']['failures']['CHECK-whole']['attempt_id'] == next_attempt['attempt_id']
        before = storage(driver.directory).read()
        for operation in (lambda: driver.run_final(), lambda: begin_procedure(driver)):
            with pytest.raises(Rejected) as error:
                operation()
            assert error.value.code == 'repair_owner_required'
            assert storage(driver.directory).read() == before
    progress = projection(driver.state)['whole_result']
    assert progress['confirmed_criteria'] == []
    assert any(gap['reason'] == ('procedure_pending' if outcome == 'pending' else outcome) for gap in progress['gaps'])
    assert compact(driver.state)['whole_result'] == progress
    assert any(item['log'] == previous['log'] for item in driver.state['final_checks']['evidence'])
    assert artifacts.is_file(driver.directory / aggregate['log'])
    final = driver.send('finalize', task_id=None)
    assert final['result'] == 'partial'
    assert 'AC-result' not in final['accepted_criteria']
    assert any(gap.get('check_id') == 'CHECK-whole' for gap in final['missing'])


def test_newer_pass_requires_aggregate_to_link_latest_procedure_attempt(project):
    driver = completed(project, procedure=True)
    previous, _ = procedure_pass(driver)
    begin_procedure(driver)
    latest = finish_procedure(driver)
    assert latest['basis'] == previous['basis'] and latest['attempt_id'] != previous['attempt_id']
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == []
    assert evidence(driver.state, driver.directory)[2][-1]['reason'] == 'procedure_superseded'
    aggregate = driver.run_final()
    assert aggregate['outcome'] == 'passed'
    output = next(item for item in driver.log(aggregate)['outputs'] if item['check_id'] == 'CHECK-whole')
    assert output['procedure_log'] == latest['log']
    assert output['procedure_log_hash'] == latest['log_hash']
    assert output['procedure_attempt'] == latest['attempt_id']
    assert driver.send('finalize', task_id=None)['result'] == 'complete'


def test_procedure_result_becomes_stale_when_integrated_head_changes(project):
    driver = completed(project, procedure=True)
    previous, _ = procedure_pass(driver)
    begin_procedure(driver)
    (project / 'integration.txt').write_text('Source changed during procedure\n', encoding='utf-8')
    stage_files(project, 'integration.txt')
    commit(project, 'Change integrated source during procedure')
    latest = finish_procedure(driver)
    assert latest['outcome'] == 'stale'
    assert latest['basis'] == previous['basis']
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == []
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.run_final()
    assert error.value.code == 'repair_owner_required'
    assert storage(driver.directory).read() == before
    assert driver.send('finalize', task_id=None)['result'] == 'partial'


def test_final_successor_explicitly_archives_interrupted_attempt_and_executes_fresh(project):
    driver = completed(project, procedure=True)
    previous, _ = procedure_pass(driver)
    interrupted = begin_procedure(driver)
    live = [role['context_id'] for role in driver.state['roles'].values()
            if role['status'] == 'active' and role['role_id'] != 'final']
    lost = driver.send('resume', dict(host_trace='synthetic-unit-test: final context disappeared mid-procedure',
                                    live_contexts=live), task_id=None)
    assert lost['status'] == 'blocked'
    assert driver.state['roles']['final']['status'] == 'lost'
    driver.final_role('successor', successor_of='final')
    resolution = dict(reason='lost_role', task_id=None, role_id='final', successor='successor',
                      evidence='Interrupted verifier did not finish; successor must execute independently')
    payload = dict(host_trace='synthetic-unit-test: fresh successor is live', live_contexts=live + ['successor'],
                   resolutions=[resolution])
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send('resume', payload, task_id=None)
    assert error.value.code == 'procedure_reconciliation'
    assert storage(driver.directory).read() == before
    resolution['abandon_procedures'] = ['CHECK-whole']
    assert driver.send('resume', payload, task_id=None)['status'] == 'active'
    assert driver.state['final_checks']['procedures'] == {}
    abandoned = driver.state['final_checks']['evidence'][-1]
    assert abandoned['outcome'] == 'abandoned' and abandoned['role_id'] == 'final'
    assert abandoned['attempt_id'] == interrupted['attempt_id']
    assert abandoned['basis'] == interrupted['basis']
    archived = driver.log(abandoned)
    assert archived['successor'] == 'successor' and archived['resolution']['evidence'] == resolution['evidence']
    assert archived['trace'] == payload['host_trace']
    assert any(item['log'] == previous['log'] for item in driver.state['final_checks']['evidence'])
    assert driver.state['final_checks']['failures'] == {}
    assert projection(driver.state)['whole_result']['confirmed_criteria'] == []
    before = storage(driver.directory).read()
    with pytest.raises(Rejected) as error:
        driver.send('procedure_result', dict(check_id='CHECK-whole', role_id='successor', outcome='passed',
                                            steps=['No attempt'], trace='synthetic-unit-test'), task_id=None)
    assert error.value.code == 'procedure_owner'
    assert storage(driver.directory).read() == before
    with pytest.raises(Rejected) as error:
        driver.send('procedure_result', dict(check_id='CHECK-whole', role_id='final', outcome='passed',
                                            steps=['Lost predecessor'], trace='synthetic-unit-test'), task_id=None)
    assert error.value.code == 'final_role'
    assert storage(driver.directory).read() == before
    fresh = begin_procedure(driver, 'successor')
    finished = finish_procedure(driver, 'successor')
    assert fresh['attempt_id'] != interrupted['attempt_id']
    assert finished['attempt_id'] == fresh['attempt_id'] and finished['role_id'] == 'successor'
    assert driver.run_final('successor')['outcome'] == 'passed'
    assert driver.send('finalize', task_id=None)['result'] == 'complete'
