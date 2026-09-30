import sys,pathlib,json,os,shutil,concurrent.futures,hashlib
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'.agents/skills/skill-conductor'))
from scripts.harness import run_prompt,save_run
ROOT=pathlib.Path((HERE/'temp-root.txt').read_text(encoding='utf-8-sig').strip())
runs=json.loads((HERE/'runs.json').read_text())
for run in runs:
 out=pathlib.Path(run['output'])
 for p in out.iterdir():
  if p.name!='prompt.txt' and p.is_file():
   dest=HERE/'native-exploratory'/run['key']/run['variant']/p.name
   dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
   # These are generated evaluation artifacts, preserved above before replacement.
   assert p.resolve().is_relative_to(HERE)
   p.unlink()
manifest=[{'path':p.relative_to(ROOT/'candidate').as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ROOT/'candidate').rglob('*') if p.is_file() and not any(x in p.parts for x in ['.venv','__pycache__','.pytest_cache'])]
(HERE/'frozen-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
os.environ['PYTHONUTF8']='1'
os.environ['UV_CACHE_DIR']=str(ROOT/'uv-cache')
pathlib.Path(os.environ['UV_CACHE_DIR']).mkdir(exist_ok=True)
def execute(run):
 out=pathlib.Path(run['output'])
 result=run_prompt((out/'prompt.txt').read_text(encoding='utf-8'),pathlib.Path(run['fixture']),'codex',None,360,False)
 save_run(result,out)
 meta=json.loads((out/'run.json').read_text(encoding='utf-8'))
 meta.update(eval_id=run['eval_id'],rep=run['rep'],variant=run['variant'],fixture=run['fixture'],isolation='Separate fixture cwd outside repo ancestors; CLI read-only sandbox. Candidate only explicitly supplied for with_skill. No global skill installs. Full discovered catalog not automatically exported; verify executor report.')
 (out/'run.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'eval':run['eval_id'],'rep':run['rep'],'variant':run['variant'],'status':result.status,'error':result.error}),flush=True)
# Micro/pressure reps precede the core and resume pairs; matching pairs run concurrently.
ordered=sorted(runs,key=lambda r:(0 if r['eval_id']==2 else r['eval_id'],r['rep'],r['variant']))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for idx in range(0,len(ordered),2):
  futures=[pool.submit(execute,run) for run in ordered[idx:idx+2]]
  for future in futures:future.result()
