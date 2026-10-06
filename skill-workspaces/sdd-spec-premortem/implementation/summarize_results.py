"""Final evidence summary after the frozen candidate's held-out gate opens."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
statuses=json.loads((HERE/'execution-status.json').read_text(encoding='utf-8'))
split=json.loads((HERE/'split.json').read_text(encoding='utf-8'))
summary={'models':{'executor_configured':'gpt-6-astra','reasoning_effort':'low','explicit_override':False,'judge':'native same-family agent'},'paired_cases':[],'transitions':{'improved':[],'regressed':[],'stable_success':[],'persistent_fail':[]},'executions':statuses}
for eid in range(13,32):
    pair={r['variant']:r for r in statuses if r['id']==eid}
    if len(pair)!=2 or any(r['status']!='completed' or not r.get('graded') for r in pair.values()):
        continue
    grades={v:json.loads((Path(r['path'])/'grading.json').read_text(encoding='utf-8-sig')) for v,r in pair.items()}
    old={e['text']:e for e in grades['old_skill']['expectations']}
    new={e['text']:e for e in grades['with_skill']['expectations']}
    summary['paired_cases'].append(eid)
    for text in old.keys() & new.keys():
        a,b=old[text]['passed'],new[text]['passed']
        category='stable_success' if a and b else 'persistent_fail' if not a and not b else 'improved' if b else 'regressed'
        summary['transitions'][category].append({'eval_id':eid,'split':'train' if eid in split['train_ids'] else 'heldout','text':text,'old_evidence':old[text]['evidence'],'new_evidence':new[text]['evidence']})
allruns=[]
for directory in HERE.iterdir():
    if directory.is_dir() and directory.name.startswith(('iteration-','micro-')):
        for file in directory.rglob('run.json'):
            if 'execution' not in file.relative_to(directory).parts:
                allruns.append(json.loads(file.read_text(encoding='utf-8-sig')))
usage={key:sum((r.get('usage') or {}).get(key,0) or 0 for r in allruns) for key in ['input_tokens','cached_input_tokens','output_tokens']}
usage.update(attempts=len(allruns),completed=sum(r['status']=='completed' for r in allruns),timed_out=sum(r['status']=='timeout' for r in allruns),unknown_usage=sum(r.get('usage') is None for r in allruns))
usage['gross_input_plus_output']=usage['input_tokens']+usage['output_tokens']
usage['uncached_input']=usage['input_tokens']-usage['cached_input_tokens']
summary['usage_all_attempts']=usage
summary['micro']={}
for variant in ['old_skill','with_skill']:
    items=[]
    for rep in range(1,6):
        path=HERE/f'micro-{rep}'/'premortem-no-scope-growth'/variant
        if (path/'run.json').exists():
            run=json.loads((path/'run.json').read_text(encoding='utf-8-sig'))
            grade=json.loads((path/'grading.json').read_text(encoding='utf-8-sig')) if (path/'grading.json').exists() else None
            items.append({'rep':rep,'status':run['status'],'summary':grade.get('summary') if grade else None})
    summary['micro'][variant]=items
summary['limitations']=['Original five timeouts retain unknown token usage; no time/token efficiency claim.','Four initial fixtures were invalidated and excluded; corrected inputs and manifests retained.','The evaluator omitted the available humanizer-ru dependency when preparing fixtures. Editorial-dependent assertions are limited by this setup error, not by a skill or environment defect; preceding persistence behavior remains observable.','Five candidate micro repetitions completed; only three baseline micro repetitions completed, two timed out. Queued micro retries explicitly held by user steering.','Independent judges are same-family, not cross-family.','The gate compares one frozen candidate, not a statistical estimate of general skill reliability.']
(HERE/'final-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
counts={k:len(v) for k,v in summary['transitions'].items()}
print(json.dumps({'matched_cases':len(summary['paired_cases']),'transitions':counts,'usage':usage},ensure_ascii=False))
