#!/usr/bin/env python3
"""Производные виды по собранным данным metrics/ (Tier-1 анализа пилота).

Вход (уже собраны make metrics): git.log, revisions.csv, coupling.csv, scc-metrics.json.
Только stdlib. Правило плана: «частота контекста» = число коммитов, затронувших
контекст (один коммит считается один раз), НЕ сумма частот файлов.
Проектная специфика — только корзины в _buckets.py; сами виды переносимы
(вид C, горячность на 100 строк, — полностью общий).

Виды:
  A. Контекстная картина: коммиты по контекстам (вся история + последние 30 дней).
  B. Cross-context co-change пары из coupling.csv.
  C. Горячность кода относительно размера: revs на 100 строк (только .kt).
  D. Ownership горячих файлов: сколько авторов и доля главного.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория

from _buckets import classify  # noqa: E402 (общая с coverage.py классификация корзин)


# --- Парсинг git.log: коммиты с датой, автором и файлами ---
# Ренеймы git фиксирует как path/{old => new}: нормализуем к новому пути,
# иначе история миграций разрезается на два «файла».
BRACE = re.compile(r'\{([^{}]+) => ([^{}]+)\}')


def normalize(path: str) -> str:
    return BRACE.sub(r'\1\2', path.replace('file://', ''))


commits = []
cur = None
for line in open(DATA / 'git.log'):
    m = re.match(r'^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.+)$', line.strip())
    if m:
        cur = {'date': m.group(2), 'author': m.group(3), 'files': []}
        commits.append(cur)
    elif cur is not None and line.count('\t') == 2:
        cur['files'].append(normalize(line.rstrip('\n').split('\t')[2]))

if not commits:
    raise SystemExit('git.log пуст или не распознан')

dates = sorted(c['date'] for c in commits)
last = date.fromisoformat(dates[-1])
recent_from = last - timedelta(days=30)

# --- A. Контекстная картина ---
per_ctx_commits = Counter()
per_ctx_recent = Counter()
per_ctx_files = Counter()
for c in commits:
    buckets = {classify(f) for f in c['files']}
    for b in buckets:
        per_ctx_commits[b] += 1
        if date.fromisoformat(c['date']) >= recent_from:
            per_ctx_recent[b] += 1
        per_ctx_files[b] += len([f for f in c['files'] if classify(f) == b])

print(f"A. Контекстная картина ({len(commits)} коммитов, {dates[0]}..{dates[-1]},"
      f" последние 30 дней с {recent_from}):")
print(f"{'коммитов':>8} {'из них 30д':>10} {'файлов затронуто':>16}  контекст")
for b, n in per_ctx_commits.most_common(20):
    print(f"{n:>8} {per_ctx_recent[b]:>10} {per_ctx_files[b]:>16}  {b}")

# --- B. Cross-context co-change пары ---
print('\nB. Cross-context co-change пары (coupling.csv, разные корзины production-кода):')
rows = list(csv.DictReader(open(DATA / 'coupling.csv')))
cross = []
for r in rows:
    a, b = classify(r['entity']), classify(r['coupled'])
    prod = lambda x: x.startswith(('ctx:', 'flat:'))
    if prod(a) and prod(b) and a != b:
        cross.append((int(r['degree']), int(r['average-revs']), r['entity'], r['coupled'], a, b))
for deg, revs, e, c, ba, bb in sorted(cross, reverse=True):
    short = lambda p: p.replace('app/src/main/kotlin/ru/tbank/gp/matcher/', '')
    print(f'{deg:>3}% revs={revs:>2}  [{ba} <-> {bb}]  {short(e)}  <->  {short(c)}')
if not cross:
    print('  (пар между разными контекстами нет)')

# --- C. Горячность относительно размера ---
revs = {r['entity']: int(r['n-revs']) for r in csv.DictReader(open(DATA / 'revisions.csv'))}
scc = json.load(open(DATA / 'scc-metrics.json'))
loc = {f['Location'].replace('file://', ''): f['Code']
       for lang in scc for f in lang.get('Files', [])}
print('\nC. Горячность кода: revs на 100 строк (только .kt, revs>=5, строк>=20):')
rated = []
for f, n in revs.items():
    if f.endswith('.kt') and n >= 5 and loc.get(f, 0) >= 20:
        rated.append((n / loc[f] * 100, n, loc[f], f))
for rate, n, code, f in sorted(rated, reverse=True)[:10]:
    print(f'{rate:>6.1f}  revs={n:<3} lines={code:<5} {f.replace("app/src/", "")}')

# --- D. Ownership горячих файлов (только существующие пути) ---
file_authors = defaultdict(Counter)
for c in commits:
    for f in set(c['files']):
        if f.endswith('.kt') and '/src/main/' in f:
            file_authors[f][c['author']] += 1

# Частоты пересчитываем из нормализованного лога: revisions.csv режет историю переименований.
revs_log = Counter()
for c in commits:
    for f in set(c['files']):
        revs_log[f] += 1
revs = {f: n for f, n in revs_log.items()}  # основной источник частоты ниже

import os

alive = lambda f: os.path.exists((ROOT / f).resolve()) or os.path.exists(ROOT / f)
dead = [(n, f) for f, n in revs.items()
        if n >= 10 and f.endswith('.kt') and '/src/main/' in f and not alive(f)]
hot = [(n, f) for f, n in revs.items()
       if n >= 10 and f.endswith('.kt') and '/src/main/' in f and alive(f)]
if dead:
    print('\nD0. Горячие пути, которых уже нет на диске (миграция flat -> контексты):')
    for n, f in sorted(dead, reverse=True):
        print(f'  revs={n:<3} {f.replace("app/src/main/kotlin/ru/tbank/gp/matcher/", "")}')
print('\nD. Ownership горячих production-файлов (revs>=10, существуют):')
for n, f in sorted(hot, reverse=True):
    if f not in file_authors:
        continue
    top_author, top_n = file_authors[f].most_common(1)[0]
    n_authors = len(file_authors[f])
    flag = '  <== bus-factor' if n_authors == 1 and n >= 15 else ''
    print(f'revs={n:<3} авторов={n_authors:<3} главный={top_n / n:>4.0%}  '
          f'{f.replace("app/src/main/kotlin/ru/tbank/gp/matcher/", "")}{flag}')

# --- E. Покрытие горячих файлов (из снимка coverage-latest.csv) ---
print('\nE. Покрытие (metrics/coverage-latest.csv; обновляется make metrics):')
LATEST = DATA / 'coverage-latest.csv'
if not LATEST.exists():
    print('  нет coverage-latest.csv — прогоните make metrics (включает тесты и jacoco)')
else:
    cov = {}
    ctx = defaultdict(lambda: [0, 0])
    total = [0, 0]
    with open(LATEST, newline='') as fh:
        for r in csv.DictReader(fh):
            f = r['file'].replace('file://', '')
            cov[f] = float(r['line_pct'])
            lc, lt = int(r['line_covered']), int(r['line_total'])
            b = classify(f)
            ctx[b][0] += lc
            ctx[b][1] += lt
            total[0] += lc
            total[1] += lt
    print(f'  всего: line {total[0] / total[1]:.0%}')
    print('  по корзинам (>=500 строк):')
    for b, (lc, lt) in sorted(ctx.items(), key=lambda x: -x[1][1]):
        if lt >= 500:
            print(f'    {lc / lt:>5.0%}  ({lt:>5} строк)  {b}')
    print('  горячие файлы x покрытие (revs>=10):')
    for n, f in sorted(hot, reverse=True)[:15]:
        c = cov.get(f)
        mark = ' <== без страховки' if c is not None and c < 0.5 and n >= 13 else ''
        print(f'    revs={n:<3} line={f"{c:.0%}" if c is not None else "?":>4}  '
              f'{f.replace("app/src/main/kotlin/ru/tbank/gp/matcher/", "")}{mark}')
