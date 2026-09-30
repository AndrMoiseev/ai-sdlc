import json, pathlib, shutil, hashlib
HERE=pathlib.Path(__file__).resolve().parent
REPO=HERE.parents[2]
ROOT=pathlib.Path((HERE/'temp-root.txt').read_text(encoding='utf-8-sig').strip())
EVALS=json.loads((REPO/'skills/sdd/evals/evals.json').read_text(encoding='utf-8'))['evals']
def write(p,t):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
for source in (REPO/'skills/sdd').rglob('*'):
 if source.is_file() and not any(x in source.parts for x in ['.pytest_cache','__pycache__']):
  dest=ROOT/'candidate'/source.relative_to(REPO/'skills/sdd');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
runs=[]
for ev in EVALS:
 for rep in range(1,6 if ev['id']==2 else 2):
  for variant in ['with_skill','without_skill']:
   key=f"eval-{ev['id']}-{ev['name']}-rep-{rep}"
   out=HERE/key/variant/'run-1';out.mkdir(parents=True,exist_ok=True)
   fixture=ROOT/'fixtures'/key/variant;fixture.mkdir(parents=True,exist_ok=True)
   prompt=f"Work only in this disposable synthetic fixture: {fixture}. Do not inspect the original repository or sibling fixtures. No file edits are required; return the requested complete artifact or concrete action response. First state whether your inherited skill catalog contains sdd, and any inherited repository instructions you can see. Do not read assertions or evaluation artifacts.\n"
   if variant=='with_skill':prompt+=f"The user explicitly selects $sdd for this task. Read and use the frozen skill at {ROOT/'candidate/SKILL.md'} and its necessary references.\n"
   prompt+=ev['prompt']
   write(out/'prompt.txt',prompt)
   write(HERE/key/'eval_metadata.json',json.dumps({'eval_id':ev['id'],'eval_name':key,'prompt':ev['prompt'],'expectations':ev['expectations']},ensure_ascii=False,indent=2))
   runs.append({'key':key,'eval_id':ev['id'],'rep':rep,'variant':variant,'output':str(out),'fixture':str(fixture),'prompt':str(out/'prompt.txt')})
write(HERE/'runs.json',json.dumps(runs,indent=2))
write(HERE/'frozen-manifest.json',json.dumps([{'path':str(p.relative_to(ROOT/'candidate')),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ROOT/'candidate').rglob('*') if p.is_file()],indent=2))
print(ROOT)
