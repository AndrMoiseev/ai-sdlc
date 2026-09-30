import json,pathlib,shutil,sys
HERE=pathlib.Path(__file__).resolve().parent
for run in json.loads((HERE/'runs.json').read_text()):
 out=pathlib.Path(run['output'])
 if not (out/'response.md').exists():continue
 (out/'outputs').mkdir(exist_ok=True)
 shutil.copy2(out/'response.md',out/'outputs/response.md')
 if (out/'artifact-validation.json').exists():shutil.copy2(out/'artifact-validation.json',out/'outputs/artifact-validation.json')
 metadata=json.loads((HERE/run['key']/'eval_metadata.json').read_text(encoding='utf-8'))
 metadata['prompt']=(out/'prompt.txt').read_text(encoding='utf-8')
 metadata.update(variant=run['variant'],repetition=run['rep'])
 (out/'eval_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
bench=HERE/'benchmark.json'
if bench.exists():
 data=json.loads(bench.read_text(encoding='utf-8'))
 data['metadata'].update(executor_model='Codex CLI configured default (no override); model name not exported',analyzer_model='Native Codex parent agents',runs_per_configuration={'1':1,'2':5,'3':1},execution_count=14,discovery='skipped: explicit-only')
 counts={}
 for run in data['runs']:
  key=(run['configuration'],run['eval_id']);counts[key]=counts.get(key,0)+1;run['run_number']=counts[key]
  source=next(r for r in json.loads((HERE/'runs.json').read_text()) if r['variant']==run['configuration'] and r['eval_id']==run['eval_id'] and r['rep']==run['run_number'])
  metrics=json.loads((pathlib.Path(source['output'])/'metrics.json').read_text(encoding='utf-8'))
  run['result']['tool_calls']=metrics['total_tool_calls']
  run['result']['errors']=None
 data['notes']=json.loads((HERE/'analysis-notes.json').read_text(encoding='utf-8')) if (HERE/'analysis-notes.json').exists() else []
 bench.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 sys.path.insert(0,str(HERE.parents[2]/'.agents/skills/skill-conductor/scripts'))
 from aggregate_benchmark import generate_markdown
 markdown=generate_markdown(data)
 markdown='\n'.join('**Evals**: 1 and 3: one paired run each; 2: five paired runs (14 total).' if line.startswith('**Evals**:') else line for line in markdown.splitlines())
 (HERE/'benchmark.md').write_text(markdown,encoding='utf-8')
