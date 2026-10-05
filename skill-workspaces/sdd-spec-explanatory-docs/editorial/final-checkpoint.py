from pathlib import Path
import hashlib, json, subprocess, sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
BASE=ROOT/'sdd/changes/sdd-spec-explanatory-docs'
parts=[]
hashes=[]
for name in ['implementation-report.md','tasks.md','state.md']:
 raw=(BASE/name).read_bytes()
 text=raw.decode('utf-8').replace('\r\n','\n')
 hashes.append({'path':str((BASE/name).relative_to(ROOT)),'sha256':hashlib.sha256(raw).hexdigest()})
 if name=='implementation-report.md':
  extract='## Локальные результаты'+text.split('## Локальные результаты',1)[1]
 elif name=='tasks.md':
  extract=text[text.index('Реализация инструкций'):text.index('## Порядок')]
 else:
  extract=text.split('## Реализация\n',1)[1].split('## Состояние до реализации',1)[0]
 parts.append('# '+name+'\n\n'+extract)
text='\n\n'.join(parts)
(OUT/'final-checkpoint-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'final-checkpoint-extract.md').write_text(text,encoding='utf-8')
(OUT/'final-checkpoint-lint-prose.md').write_text(text.replace('свидетельства','ТЕРМИН').replace('свидетельств','ТЕРМИН'),encoding='utf-8')
for name in ['final-checkpoint-extract.md','final-checkpoint-lint-prose.md']:
 run=subprocess.run([sys.executable,str(ROOT/'.agents/skills/humanizer-ru/scripts/lint.py'),str(OUT/name)],capture_output=True,text=True,encoding='utf-8')
 (OUT/(name+'.lint.txt')).write_text(run.stdout+run.stderr,encoding='utf-8')
 print(name,run.stdout)
