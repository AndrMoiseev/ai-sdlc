"""Exercise unchanged snapshot/check boundaries on disposable fixtures."""
import json
import subprocess
import sys
from pathlib import Path
from fixtures import prepare_fixture

work = Path(__file__).resolve().parent
launcher = work.parents[2] / 'skills/sdd-spec/scripts/run.py'
fixture = work / 'authority-probe'
prepare_fixture(fixture, 28)
change = fixture / 'sdd/changes/delivery-report'

def run(command, tag):
    result = subprocess.run([sys.executable, str(launcher), command,
                             '--project-root', str(fixture), '--change', 'delivery-report',
                             '--stage', 'documents'], capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    (work / f'authority-{tag}.json').write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'{tag}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return json.loads(result.stdout)

before = run('snapshot', 'before')
before_check = run('check', 'before-check')
research = change / 'premortem.md'
research.write_text(research.read_text(encoding='utf-8') + '\nУточнение источника: решение принимается на утренней сессии.\n', encoding='utf-8')
research_only = run('snapshot', 'research-only')
research_check = run('check', 'research-only-check')
assert before == research_only, 'Research changed normative snapshot'
for relative in ('proposal.md', 'design.md', 'specs/main/spec.md'):
    path = change / relative
    path.write_text(path.read_text(encoding='utf-8').replace('08:00', '07:00'), encoding='utf-8')
normative = run('snapshot', 'normative')
normative_check = run('check', 'normative-check')
assert normative != before, 'Normative behavior did not change snapshot'
(work / 'authority-results.json').write_text(json.dumps(dict(
    research_preserves_manifest=before == research_only,
    normative_changes_manifest=normative != before,
    before_review=before_check.get('review_status'),
    research_review=research_check.get('review_status'),
    normative_review=normative_check.get('review_status'),
    before_approval=before_check.get('approval_status'),
    normative_approval=normative_check.get('approval_status'),
), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('Snapshot and documents-check probes completed; see authority-results.json')
