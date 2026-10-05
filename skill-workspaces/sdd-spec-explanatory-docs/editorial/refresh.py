from pathlib import Path
import hashlib, json, subprocess, sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
new={'flows/explain.md','references/explanation.md','templates/explanation.md','templates/preview-handoff.md'}
manifest=json.loads((OUT/'source-hashes.json').read_text(encoding='utf-8'))
parts=[]
hashes=[]
for entry in manifest:
 path=entry['path']
 raw=(ROOT/path).read_bytes()
 text=raw.decode('utf-8')
 hashes.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
 if path.startswith('skills/sdd-spec/'):
  rel=path.removeprefix('skills/sdd-spec/')
  if rel in new:
   extract=text
  elif rel=='evals/evals.json':
   extract='\n\n'.join('\n'.join([e['prompt'],e['expected_output'],*e['expectations']]) for e in json.loads(text)['evals'] if e['id']>=4)
  else:
   diff=subprocess.check_output(['git','diff','--unified=0','--',path],cwd=ROOT).decode('utf-8')
   extract='\n'.join(line[1:] for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
 elif path.endswith('/tasks.md'):
  extract=text[text.index('Реализация инструкций'):text.index('## Порядок')]
 elif path.endswith('/state.md'):
  extract=text.split('## Реализация\n',1)[1].split('## Состояние до реализации',1)[0]
 else:
  extract=text
 parts.append('## '+path+'\n\n'+extract)
 target=OUT/'final-v2'/path
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(raw)
text='\n\n'.join(parts)
(OUT/'final-v2-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'extracted-final-v2.md').write_text(text,encoding='utf-8')
(OUT/'lint-prose-v2.md').write_text(text.replace('свидетельства','ТЕРМИН').replace('свидетельств','ТЕРМИН'),encoding='utf-8')
for name in ['extracted-final-v2.md','lint-prose-v2.md','visibility-followup.md']:
 run=subprocess.run([sys.executable,str(ROOT/'.agents/skills/humanizer-ru/scripts/lint.py'),str(OUT/name)],capture_output=True,text=True,encoding='utf-8')
 (OUT/(name+'.lint.txt')).write_text(run.stdout+run.stderr,encoding='utf-8')
 print(name,run.stdout.split('итого:',1)[-1].strip())
