from pathlib import Path
import hashlib
import json
import re

repo = Path(__file__).resolve().parents[4]
root = repo / 'sdd/changes/sdd-spec-premortem'
out = Path(__file__).resolve().parent
files = ['proposal.md', 'specs/premortem/spec.md', 'design.md', 'premortem.md', 'state.md']
mapping = {}
hashes = {}
links = 0
for relative in files:
    path = root / relative
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    hashes[relative] = hashlib.sha256(raw).hexdigest()
    body = re.sub(r'\A---\n.*?\n---\n', '', text.replace('\r\n', '\n'), count=1, flags=re.S)
    body = body.split('Служебная отметка:')[0]
    fields = []
    for block in re.findall(r'```yaml\n(.*?)```', body, re.S):
        record_id = re.search(r'^id: (.+)$', block, re.M).group(1)
        for field, value in re.findall(r'^(conditions|expected|text|reason|return_at): (.+)$', block, re.M):
            fields.append({'id': record_id, 'field': field, 'text': value.strip("'\"")})
    body = re.sub(r'```.*?```', '', body, flags=re.S)
    body = re.sub(r'^>.*$', '', body, flags=re.M)
    for dest in re.findall(r'\]\(([^)]+)\)', body):
        if not dest.startswith(('https://', 'http://', '#')):
            target = (path.parent / dest.split('#')[0]).resolve()
            assert target.exists(), (relative, dest)
            links += 1
    body = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', body)
    name = relative.replace('/', '__') + '.prose.md'
    (out / name).write_text(body + '\n' + '\n'.join(f['text'] for f in fields) + '\n', encoding='utf-8')
    mapping[name] = {'source': relative, 'yaml_fields': fields}
(out / 'source-map.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
print(json.dumps({'files': len(files), 'valid_local_links': links, 'requirements': (root / files[1]).read_text(encoding='utf-8').count('sdd_record: requirement'), 'acceptance': (root / files[1]).read_text(encoding='utf-8').count('sdd_record: acceptance')}))
