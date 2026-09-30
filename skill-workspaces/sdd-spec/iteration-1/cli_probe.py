import sys,pathlib,json
here=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(here.parents[2]/'.agents/skills/skill-conductor'))
from scripts.harness import run_prompt,save_run
root=pathlib.Path((here/'temp-root.txt').read_text(encoding='utf-8-sig').strip())
result=run_prompt('Read-only runtime probe. Return only READY. Do not inspect files or use tools.',root/'fixtures/eval-2-stale-review-pressure-rep-3/without_skill','codex',None,60,False)
save_run(result,here/'cli-probe')
print(json.dumps({'status':result.status,'error':result.error}))
