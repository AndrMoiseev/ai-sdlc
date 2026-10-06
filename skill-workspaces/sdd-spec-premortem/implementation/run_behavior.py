"""Disposable explicit behavior runs; no evaluation expectations reach executors."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNNER = REPO / 'skills/sdd-skill-conductor/scripts/run_task.py'
os.environ['PYTHONDONTWRITEBYTECODE']='1'


def run_one(case, args):
    from fixtures import prepare_fixture
    out = HERE / args.iteration / case['name'] / args.variant
    if out.exists():
        raise RuntimeError(f'Refusing to overwrite {out}')
    out.mkdir(parents=True)
    fixture = Path(tempfile.mkdtemp(prefix=f'sdd-premortem-{args.variant}-{case["id"]}-'))
    prepare_fixture(fixture, case['id'])
    initial=[{'path':f.relative_to(fixture).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(fixture.rglob('*')) if f.is_file()]
    (out/'fixture-manifest.json').write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding='utf-8')
    required_files = []
    if args.variant != 'without_skill':
        package = Path(args.skill).resolve() if args.skill else HERE / 'baseline'
        shutil.copytree(package, fixture / '.agents/skills/sdd-spec')
        dependency = REPO / '.agents/skills/humanizer-ru'
        shutil.copytree(dependency, fixture / '.agents/skills/humanizer-ru',
                        ignore=shutil.ignore_patterns('__pycache__', '.venv', '.pytest_cache'))
        required_files = ['.agents/skills/sdd-spec/SKILL.md',
                          '.agents/skills/humanizer-ru/SKILL.md',
                          '.agents/skills/humanizer-ru/references/patterns.md',
                          '.agents/skills/humanizer-ru/scripts/lint.py']
    resource_manifest = out / 'required-resources.json'
    resource_manifest.write_text(json.dumps({'schema_version': 1, 'required_files': required_files,
                                             'expected_missing_files': []}, indent=2), encoding='utf-8')
    prompt = case['prompt']
    if args.variant == 'without_skill':
        prompt = prompt.replace('$sdd-spec ', '')
    else:
        prompt += '\n\nИспользуй локальный .agents/skills/sdd-spec/SKILL.md и необходимые материалы этого пакета.'
    prompt += '\nРабочая папка содержит все доступные материалы проекта. Сохрани результат работы в ней. Не изменяй код реализации.'
    (out / 'prompt.txt').write_text(prompt, encoding='utf-8')
    (out / 'fixture.json').write_text(json.dumps({'path': str(fixture), 'eval_id': case['id']}, indent=2), encoding='utf-8')
    (out.parent / 'eval_metadata.json').write_text(json.dumps({'eval_id': case['id'], 'eval_name': case['name'], 'prompt':case['prompt'], 'expectations':case['expectations']}, ensure_ascii=False, indent=2), encoding='utf-8')
    command = ['uv', 'run', str(RUNNER), '--harness', 'codex', '--prompt-file', str(out/'prompt.txt'), '--workspace', str(fixture), '--fixture-manifest', str(resource_manifest), '--output-dir', str(out/'execution'), '--timeout',str(args.timeout), '--allow-writes']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (out/'launcher.txt').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    for name in ['preflight.json','response.md','stdout.jsonl','stderr.txt','run.json','timing.json']:
        source = out/'execution'/name
        if source.exists():
            shutil.copy2(source, out/name)
    if (fixture/'sdd').exists():
        shutil.copytree(fixture/'sdd',out/'outputs/sdd')
    (out/'outputs').mkdir(exist_ok=True)
    if (out/'response.md').exists():
        shutil.copy2(out/'response.md',out/'outputs/response.md')
    combined=[]
    for artifact in sorted((fixture/'sdd').rglob('*.md')):
        combined.append(f'\n\n# {artifact.relative_to(fixture).as_posix()}\n\n'+artifact.read_text(encoding='utf-8-sig'))
    (out/'outputs/artifacts.md').write_text(''.join(combined),encoding='utf-8')
    if case['id'] == 28 and result.returncode == 0:
        followup = out/'followup-prompt.txt'
        followup.write_text('$sdd-spec Я выбираю время отчёта 07:00 вместо 08:00. Обнови нормативные документы и состояние согласований. Используй .agents/skills/sdd-spec/SKILL.md. Реализацию не начинай.',encoding='utf-8')
        followcommand=command.copy()
        followcommand[followcommand.index('--prompt-file')+1]=str(followup)
        followcommand[followcommand.index('--output-dir')+1]=str(out/'followup')
        followresult=subprocess.run(followcommand,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (out/'followup-launcher.txt').write_text(followresult.stdout+'\n'+followresult.stderr,encoding='utf-8')
        if (fixture/'sdd').exists():
            shutil.copytree(fixture/'sdd',out/'followup-outputs/sdd')
    print(json.dumps({'id':case['id'],'variant':args.variant,'exit':result.returncode,'out':str(out)},ensure_ascii=False),flush=True)
    return result.returncode


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ids',default=','.join(map(str,range(13,32))))
    p.add_argument('--variant',choices=['old_skill','with_skill','without_skill'],default='old_skill')
    p.add_argument('--iteration',default='iteration-1')
    p.add_argument('--skill')
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--timeout',type=int,default=480)
    args=p.parse_args()
    cases=json.loads((HERE/'planned-evals.json').read_text(encoding='utf-8'))['evals']
    selected={int(x) for x in args.ids.split(',')}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_one,e,args) for e in cases if e['id'] in selected]
        codes=[]
        for future in concurrent.futures.as_completed(futures):
            codes.append(future.result())
    raise SystemExit(max(codes,default=0))
