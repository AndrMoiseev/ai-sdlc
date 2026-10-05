from pathlib import Path
import hashlib, json, re, subprocess, importlib.util

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
new = ['flows/explain.md', 'references/explanation.md', 'templates/explanation.md', 'templates/preview-handoff.md']
changed = ['SKILL.md', 'README.md', 'flows/draft.md', 'flows/resume.md', 'flows/revise.md', 'references/runtime-setup.md', 'references/document-format.md', 'references/editorial-pass.md', 'evals/manual.md', 'evals/evals.json']
changes = {
 'references/explanation.md': [
  ('Удалённый шаг\nне выглядит исполняемым в будущем процессе.', 'Не показывай удалённый шаг\nкак исполняемый в будущем процессе.', 4),
  ('index.md является обычным Markdown, без нового `document_type`.', 'index.md - обычный Markdown, без нового `document_type`.', 3),
  ('Примеры синтаксиса в шаблоне являются образцами,\nа реальные пути всегда берутся из результата проверки.', 'В шаблоне приведены образцы синтаксиса;\nреальные пути всегда бери из результата проверки.', 3),
  ('Правка, добавление или удаление proposal/design/specs делает пояснение\nтребующим сверки.', 'Правка, добавление или удаление proposal/design/specs требует\nсверки пояснения.', 1),
 ],
 'templates/preview-handoff.md': [
  ('Доступность браузера включает\n   локальный Chrome/Chromium.', 'При проверке доступности браузера учитывай\n   локальный Chrome/Chromium.', 36),
  ('смена среды не является исправлением содержательного дефекта.', 'смена среды не исправляет содержательный дефект.', 1),
 ],
 'flows/revise.md': [
  ('Правка только производных материалов не устаревает согласование неизменённых нормативных документов.', 'Правка только производных материалов не делает устаревшим согласование неизменённых нормативных документов.', 36),
 ],
}
replacements=[]
manifest=[]
extractions={}
final_dir=OUT/'final'
final_dir.mkdir(exist_ok=True)
for rel in new+changed:
 path='skills/sdd-spec/'+rel
 raw=(ROOT/path).read_bytes()
 source=raw.decode('utf-8')
 manifest.append({'path':path, 'sha256':hashlib.sha256(raw).hexdigest()})
 final=source
 for old,replacement,pattern in changes.get(rel,[]):
  assert final.count(old)==1, (path,old)
  replacements.append({'path':path,'old':old,'new':replacement,'pattern':pattern})
  final=final.replace(old,replacement)
 target=final_dir/path
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(final.encode('utf-8'))
 if rel in new:
  extract=final
 elif rel=='evals/evals.json':
  data=json.loads(final)
  extract='\n\n'.join('\n'.join([e['prompt'], e['expected_output'], *e['expectations']]) for e in data['evals'] if e['id']>=4)
 else:
  diff=subprocess.check_output(['git','diff','--unified=0','--',path],cwd=ROOT).decode('utf-8')
  extract='\n'.join(line[1:] for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
  for old,replacement,pattern in changes.get(rel,[]):
   assert old in extract
   extract=extract.replace(old,replacement)
 extractions[path]=extract
change_root='sdd/changes/sdd-spec-explanatory-docs/'
for rel in ['implementation-report.md','tasks.md','state.md']:
 path=change_root+rel
 raw=(ROOT/path).read_bytes()
 source=raw.decode('utf-8')
 manifest.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
 if rel=='tasks.md':
  extract=source[source.index('Реализация инструкций'):source.index('## Порядок')]
 elif rel=='state.md':
  extract=source.split('## Реализация\n',1)[1].split('## Состояние до реализации',1)[0]
 else:
  extract=source
 extractions[path]=extract
 target=final_dir/path
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(raw)

(OUT/'source-hashes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'replacements.json').write_text(json.dumps(replacements,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'extracted-final.md').write_text('\n\n'.join('## '+p+'\n\n'+x for p,x in extractions.items()),encoding='utf-8')
print(f'{len(manifest)} files, {len(replacements)} replacements')
