"""Fill shipped templates and validate their shared contract end to end."""
from pathlib import Path
from copy import deepcopy

import yaml

from lib.documents import read_document
from lib.reviews import review_status
from lib.snapshots import snapshot
from lib.validation import validate_documents
from test_check_command import create_project, SKILL


def write_frontmatter(path, meta, body=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + body, encoding='utf-8')


def test_two_capabilities_and_filled_review_templates(tmp_path):
    change = create_project(tmp_path)
    second_spec = change / 'specs/second-capability/spec.md'
    second_spec.parent.mkdir(parents=True)
    second_spec.write_text((change / 'specs/sample-capability/spec.md').read_text(encoding='utf-8')
                          .replace('sample-capability', 'second-capability')
                          .replace('REQ-sample-behavior', 'REQ-second-behavior')
                          .replace('AC-sample-result', 'AC-second-result'), encoding='utf-8')
    tasks = change / 'tasks.md'
    task_text = tasks.read_text(encoding='utf-8')
    task_text += '\n' + task_text.split('# План реализации\n', 1)[1].replace(
        'TASK-sample-result', 'TASK-second-result').replace('AC-sample-result', 'AC-second-result').replace('number: 1', 'number: 2')
    tasks.write_text(task_text, encoding='utf-8')
    assert not validate_documents(tmp_path, change, 'plan')['errors']
    inputs = snapshot(tmp_path, 'sample-change', 'plan')
    report = read_document(SKILL / 'templates/review-report.md').meta
    report.update(stage='plan_review', lens_id='plan', result='completed_no_findings',
                  limitations=[], inputs=inputs, inputs_after=deepcopy(inputs), freshness='current')
    write_frontmatter(change / f'review/{report["run_id"]}/plan.md', report)
    summary = read_document(SKILL / 'templates/review-summary.md').meta
    write_frontmatter(change / 'review/summary.md', summary)
    decision_meta = read_document(SKILL / 'templates/decisions.md').meta
    decision = dict(sdd_record='user', id='USER-approve-plan', kind='plan_approval',
                    scope={'stage': 'plan_review'}, response='Согласован именно этот комплект',
                    date='2026-01-01T01:00:00Z', inputs=inputs)
    write_frontmatter(change / 'review/decisions.md', decision_meta,
                      '\n### Согласование\n\n```yaml\n' + yaml.safe_dump(decision, allow_unicode=True) + '```\n')
    state = read_document(SKILL / 'templates/state.md').meta
    state.update(phase='plan_approved', awaiting='none', document_links=['proposal.md', 'tasks.md'],
                 approval_refs=['USER-approve-plan'], review_links=[f'review/{report["run_id"]}/plan.md'])
    write_frontmatter(change / 'state.md', state)
    result = review_status(tmp_path, change, 'plan')
    assert result['errors'] == []
    assert result['warnings'] == []
    assert result['review_status']['complete'] is True
    assert result['approval_status']['ready'] is True
    # Checkpoint/review metadata are excluded from the normative byte manifest.
    assert snapshot(tmp_path, 'sample-change', 'plan') == inputs
