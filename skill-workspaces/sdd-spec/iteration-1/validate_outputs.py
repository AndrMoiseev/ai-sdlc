"""Validate returned plans in separate copies; preserve execution fixtures and answers."""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'skills/sdd-spec/scripts'))
from lib.validation import validate_documents

results = []
for run in json.loads((HERE / 'runs.json').read_text(encoding='utf-8')):
    if run['eval_id'] != 1:
        continue
    target = HERE / 'artifact-check' / run['variant']
    shutil.copytree(run['fixture'], target, dirs_exist_ok=True)
    answer = (Path(run['output']) / 'response.md').read_text(encoding='utf-8')
    change = target / 'sdd/changes/sample-change'
    (change / 'tasks.md').write_text(answer, encoding='utf-8')
    validation = validate_documents(target, change, 'plan')
    results.append({'variant': run['variant'], 'validation': validation})
(HERE / 'artifact-validation.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
