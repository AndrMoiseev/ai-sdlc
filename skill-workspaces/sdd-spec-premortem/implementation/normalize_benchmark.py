"""Correct generic aggregator placeholders and explicit candidate-minus-baseline delta."""
import argparse
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('path',type=Path)
args=p.parse_args()
data=json.loads(args.path.read_text(encoding='utf-8-sig'))
data['metadata'].update(skill_path='skills/sdd-spec',executor_model='gpt-6-astra',analyzer_model='native Codex agent (same family)',runs_per_configuration=1)
data['metadata']['executor_reasoning_effort']='low'
data['metadata']['executor_model_note']='Root verified gpt-6-astra and low in user config. Both variants use this configured CLI default; run.json model remains null because no explicit override was requested.'
data['metadata']['pairing']='Only valid, completed, independently graded matched pairs are included.'
data['metadata']['delta_direction']='with_skill minus old_skill'
data['metadata']['limitations']=['Some baseline runs were controlled retries at1200s after480s timeout; no speed benefit is claimed.','The independent grader is not cross-family.','Fixture preparation omitted the available humanizer-ru dependency. This is an evaluation setup error, not a skill or environment defect; editorial-dependent outcomes are limited.']
summary=data['run_summary']
for metric,precision in [('pass_rate',4),('time_seconds',1),('tokens',0)]:
    new=summary.get('with_skill',{}).get(metric,{}).get('mean')
    old=summary.get('old_skill',{}).get(metric,{}).get('mean')
    summary['delta'][metric]=f'{new-old:+.{precision}f}' if new is not None and old is not None else None
for run in data['runs']:
    # The generic aggregator defaults missing telemetry to zero; preserve unknown.
    run['result']['tool_calls']=None
    run['result']['errors']=None
args.path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Matched behavioral benchmark','','One completed graded run per configuration and scenario. Candidate minus baseline is the delta direction.','',f"Matched scenarios: {len(data['metadata']['evals_run'])}.",'']
for variant in ['old_skill','with_skill']:
    stats=summary.get(variant,{}).get('pass_rate',{})
    lines.append(f"- {variant}: mean per-scenario pass rate {stats.get('mean')}; n={stats.get('n')}.")
lines+=['',f"Pass-rate delta: {summary['delta'].get('pass_rate')}.",'','No efficiency claim: some baseline attempts required longer timeout retries. See final-summary.json for gross usage and all limitations.']
args.path.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
