"""Assemble valid paired evidence; does not invent grades for incomplete runs."""
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
def artifact_text(source,name):
    text=(source/name).read_text(encoding='utf-8-sig')
    if name=='timing.json' and (source/'followup/timing.json').exists():
        timing=json.loads(text)
        follow=json.loads((source/'followup/timing.json').read_text(encoding='utf-8-sig'))
        for key in ['duration_ms','total_duration_seconds','total_tokens']:
            timing[key]=timing[key]+follow[key] if timing.get(key) is not None and follow.get(key) is not None else None
        timing['includes_followup']=True
        return json.dumps(timing,indent=2)
    return text
cases=json.loads((HERE/'planned-evals.json').read_text(encoding='utf-8'))['evals']
split=json.loads((HERE/'split.json').read_text(encoding='utf-8'))
destination=HERE/'comparison'
statuses=[]
for case in cases:
    if case['id']<13:
        continue
    for variant in ['old_skill','with_skill']:
        iteration='iteration-2' if variant=='with_skill' else 'iteration-1-corrected' if case['id'] in {13,14,16,20} else 'iteration-1'
        if variant=='old_skill' and case['id'] in {13,14,19} and (HERE/'iteration-1-retry'/case['name']/variant).exists():
            iteration='iteration-1-retry'
        source=HERE/iteration/case['name']/variant
        if not (source/'run.json').exists():
            statuses.append({'id':case['id'],'variant':variant,'status':'pending'})
            continue
        run=json.loads((source/'run.json').read_text(encoding='utf-8'))
        if case['id']==28 and run['status']=='completed':
            if not (source/'followup/run.json').exists():
                run['status']='pending_followup'
            else:
                follow=json.loads((source/'followup/run.json').read_text(encoding='utf-8'))
                run['status']=follow['status']
                run['duration_ms']+=follow['duration_ms']
        statuses.append({'id':case['id'],'variant':variant,'status':run['status'],'duration_ms':run['duration_ms'],'path':str(source),'graded':(source/'grading.json').exists()})
        target=destination/case['name']/variant
        shutil.copytree(source,target,dirs_exist_ok=True)
        if (target/'grading.json').exists():
            (target/'grading.json').write_text((target/'grading.json').read_text(encoding='utf-8-sig'),encoding='utf-8')
        shutil.copy2(source.parent/'eval_metadata.json',target.parent/'eval_metadata.json')
        if (source/'grading.json').exists() and run['status']=='completed':
            for group in ['benchmark-inputs']+(['train-benchmark-inputs'] if case['id'] in split['train_ids'] else []):
                bench=HERE/group/f'eval-{case["id"]}-{case["name"]}'/variant/'run-1'
                bench.mkdir(parents=True,exist_ok=True)
                for name in ['grading.json','timing.json']:
                    (bench/name).write_text(artifact_text(source,name),encoding='utf-8')
                shutil.copy2(source.parent/'eval_metadata.json',bench.parent.parent/'eval_metadata.json')
        # Training viewer never includes held-out evidence.
        if case['id'] in split['train_ids']:
            train=HERE/'train-comparison'/case['name']/variant
            shutil.copytree(source,train,dirs_exist_ok=True)
            if (train/'grading.json').exists():
                (train/'grading.json').write_text((train/'grading.json').read_text(encoding='utf-8-sig'),encoding='utf-8')
            shutil.copy2(source.parent/'eval_metadata.json',train.parent/'eval_metadata.json')
(HERE/'execution-status.json').write_text(json.dumps(statuses,ensure_ascii=False,indent=2),encoding='utf-8')
counts={}
for item in statuses:
    key=item['variant']+':'+item['status']
    counts[key]=counts.get(key,0)+1
for case in cases:
    if case['id']<13:
        continue
    pair=[i for i in statuses if i['id']==case['id']]
    if len(pair)!=2 or any(i['status']!='completed' or not i.get('graded') for i in pair):
        continue
    for item in pair:
        source=Path(item['path'])
        groups=['matched-benchmark-inputs']+(['matched-train-benchmark-inputs'] if case['id'] in split['train_ids'] else [])
        for group in groups:
            target=HERE/group/f'eval-{case["id"]}-{case["name"]}'/item['variant']/'run-1'
            target.mkdir(parents=True,exist_ok=True)
            for name in ['grading.json','timing.json']:
                (target/name).write_text(artifact_text(source,name),encoding='utf-8')
            shutil.copy2(source.parent/'eval_metadata.json',target.parent.parent/'eval_metadata.json')
print(json.dumps(counts))
