from pathlib import Path
import hashlib
import json
import re

repo = Path(__file__).resolve().parents[4]
root = repo / 'sdd/changes/sdd-spec-premortem'
out = Path(__file__).resolve().parent
mapping, hashes = {}, {}
links = 0
for relative in ['tasks.md', 'state.md']:
    path = root / relative
    raw = path.read_bytes()
    hashes[relative] = hashlib.sha256(raw).hexdigest()
    text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    body = re.sub(r'\A---\n.*?\n---\n', '', text, count=1, flags=re.S)
    body = body.split('Служебная отметка:')[0]
    fields = []
    for block in re.findall(r'```yaml\n(.*?)```', body, re.S):
        record_id = re.search(r'^id: (.+)$', block, re.M).group(1)
        verification = -1
        for field, value in re.findall(r'^\s*(test_description|setup_required|text|reason|return_at): (.+)$', block, re.M):
            if field == 'test_description':
                verification += 1
            name = field if verification < 0 else f'verification[{verification}].{field}'
            fields.append({'id': record_id, 'field': name, 'text': value.strip("'\"")})
    body = re.sub(r'```.*?```', '', body, flags=re.S)
    body = re.sub(r'^>.*$', '', body, flags=re.M)
    for dest in re.findall(r'\]\(([^)]+)\)', body):
        if not dest.startswith(('https://', 'http://', '#')):
            assert (path.parent / dest.split('#')[0]).resolve().exists(), (relative, dest)
            links += 1
    body = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', body)
    name = relative + '.prose.md'
    (out / name).write_text(body + '\n' + '\n'.join(f['text'] for f in fields) + '\n', encoding='utf-8')
    mapping[name] = {'source': relative, 'yaml_fields': fields}
(out / 'source-map.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
print(json.dumps({'files': 2, 'valid_local_links': links, 'hashes': hashes}))
