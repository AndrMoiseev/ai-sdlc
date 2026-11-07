#!/usr/bin/env python3
"""Мост «структура × история» по метрикам пилота.

Три вида, все на production-коде (`src/main`, .kt):
  1. Горячие точки: видимость классов (транзитивный fan-in, propagation)
     × ревизии/churn — «изменить здесь — дорого всей системе».
  2. Fan-out сторона: транзитивный охват импортов × ревизии/churn —
     «часто правимые файлы, зависящие от многого»: первыми чувствуют
     движение контрактов и типов.
  3. Неявная связность: co-change пары (metrics/coupling.csv) без
     статической связи между файлами — сцепка через общий контракт.

Класс -> файл по пути `app/src/main/kotlin/<package>/<Name>.kt` (классы
вне этой схемы не учтены); видимость/охват файла = max по его классам.
Мёртвые пути истории видимости не имеют — граф строился по текущей сборке.
Метрики обобщённые (статический граф + история git); JVM-специфика —
только маппинг класс->файл по конвенции путей.
"""
import csv
import re
from collections import Counter
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория
PREFIX = 'app/src/main/kotlin/'
BRACE = re.compile(r'\{([^{}]+) => ([^{}]+)\}')
HDR = re.compile(r'^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.+)$')

# --- git.log: ревизии и churn по файлам (пути нормализуем, как report.py) ---
revs: Counter = Counter()
churn: Counter = Counter()
cur_files: list[str] = []
for line in open(DATA / 'git.log'):
    m = HDR.match(line.strip())
    if m:
        for f in cur_files:
            revs[f] += 1
        cur_files = []
    elif '\t' in line:
        parts = line.rstrip('\n').split('\t')
        if len(parts) == 3:
            f = BRACE.sub(r'\1\2', parts[2])
            if f.endswith('.kt') and '/src/main/' in f:
                cur_files.append(f)
                if parts[0] != '-' and parts[1] != '-':
                    churn[f] += int(parts[0]) + int(parts[1])
for f in cur_files:
    revs[f] += 1

# --- deps-class.csv: обратная достижимость = видимость класса ---
adj: dict[str, set[str]] = {}
with open(DATA / 'deps-class.csv', newline='') as fh:
    for r in csv.DictReader(fh):
        adj.setdefault(r['from'], set()).add(r['to'])
        adj.setdefault(r['to'], set())
n = len(adj)
radj: dict[str, set[str]] = {v: set() for v in adj}
for a, bs in adj.items():
    for b in bs:
        radj[b].add(a)

vis: dict[str, int] = {}
for v in adj:
    seen = {v}
    stack = [v]
    while stack:
        for w in radj[stack.pop()]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    vis[v] = len(seen)

file_vis: dict[str, tuple[float, str]] = {}
mapped = 0
for cls, k in vis.items():
    f = PREFIX + cls.replace('.', '/') + '.kt'
    if f in revs or (ROOT / f).exists():
        mapped += 1
        frac = k / n
        if f not in file_vis or frac > file_vis[f][0]:
            file_vis[f] = (frac, cls)

print(f'классов в графе: {n}; смаплено на файлы: {mapped}; production-файлов в истории: '
      f'{sum(1 for f in revs if file_vis.get(f))}')

alive = lambda f: (ROOT / f).exists()
rows = [(frac * revs.get(f, 0), frac * churn.get(f, 0), f, frac, cls, revs.get(f, 0), churn.get(f, 0))
        for f, (frac, cls) in file_vis.items() if revs.get(f, 0) > 0 and alive(f)]

print('\n=== Горячие точки: видимость × коммиты (топ-15, живые файлы) ===')
print(f'{"score":>6} {"видим.":>7} {"ревизий":>8} {"churn":>7}  класс/файл')
for s1, s2, f, frac, cls, r, ch in sorted(rows, reverse=True)[:15]:
    print(f'{s1:>6.1f} {frac:>7.1%} {r:>8} {ch:>7}  {cls.split("matcher.")[-1]}')

print('\n=== Горячие точки: видимость × переписанные строки (топ-15) ===')
for s1, s2, f, frac, cls, r, ch in sorted(rows, key=lambda x: -x[1])[:15]:
    print(f'{s2:>6.1f} {frac:>7.1%} {r:>8} {ch:>7}  {cls.split("matcher.")[-1]}')

hot = [x for x in rows if x[5] >= 10]
print(f'\n=== Часто меняемые файлы (revs>=10): {len(hot)}; из них видимость >= 5%: '
      f'{sum(1 for x in hot if x[3] >= 0.05)}, >= 10%: {sum(1 for x in hot if x[3] >= 0.10)} ===')
for s1, s2, f, frac, cls, r, ch in sorted(hot, key=lambda x: -x[3])[:10]:
    print(f'  {frac:>6.1%} видимости, revs={r:<3} {cls.split("matcher.")[-1]}')

# --- Fan-out сторона: транзитивный охват импортов (что файл тянет за собой) ---
reach_out: dict[str, int] = {}
for v in adj:
    seen = {v}
    stack = [v]
    while stack:
        for w in adj[stack.pop()]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    reach_out[v] = len(seen)

file_out: dict[str, tuple[float, str]] = {}
for cls, k in reach_out.items():
    f = PREFIX + cls.replace('.', '/') + '.kt'
    if f in revs or (ROOT / f).exists():
        frac = k / n
        if f not in file_out or frac > file_out[f][0]:
            file_out[f] = (frac, cls)

print('\n=== Fan-out сторона: охват импортов × коммиты (топ-12, живые) ===')
print('«часто правят И зависит от многого — первым чувствует движение контрактов»')
rows_out = [(frac * revs.get(f, 0), frac * churn.get(f, 0), f, frac, cls, revs.get(f, 0), churn.get(f, 0))
            for f, (frac, cls) in file_out.items() if revs.get(f, 0) > 0 and alive(f)]
for s1, s2, f, frac, cls, r, ch in sorted(rows_out, reverse=True)[:12]:
    print(f'{s1:>6.1f} {frac:>7.1%} {r:>8} {ch:>7}  {cls.split("matcher.")[-1]}')

# --- Неявная связность: co-change без статической связи ---
cls_file = {c: PREFIX + c.replace('.', '/') + '.kt'
            for c in adj if (PREFIX + c.replace('.', '/') + '.kt') in revs or (ROOT / (PREFIX + c.replace('.', '/') + '.kt')).exists()}
file_edges = set()
for a, bs in adj.items():
    if a in cls_file:
        for b in bs:
            if b in cls_file:
                file_edges.add((cls_file[a], cls_file[b]))

pkg_deps: dict[str, set[str]] = {}
for a, bs in adj.items():
    if a in cls_file:
        pkg_deps.setdefault(cls_file[a], set()).update(
            b.rsplit('.', 1)[0] for b in bs)

implicit, dead_implicit = [], 0
for r in csv.DictReader(open(DATA / 'coupling.csv')):
    e, c = r['entity'], r['coupled']
    if not (e.endswith('.kt') and c.endswith('.kt')):
        continue
    if '/src/main/' not in e or '/src/main/' not in c:
        continue
    if (e, c) in file_edges or (c, e) in file_edges:
        continue
    if e.rsplit('/', 1)[0] == c.rsplit('/', 1)[0]:
        continue  # один пакет — структурная общность есть
    if not ((ROOT / e).exists() and (ROOT / c).exists()):
        dead_implicit += 1
        continue
    common = pkg_deps.get(e, set()) & pkg_deps.get(c, set())
    top_common = ', '.join(sorted(x.replace('ru.tbank.gp.matcher.', '') for x in common)[:2])
    implicit.append((int(r['degree']), int(r['average-revs']),
                     e.split('matcher/')[-1], c.split('matcher/')[-1], top_common or '—'))

print(f'\n=== Неявная связность: co-change без статического ребра (живые; мёртвых пар: {dead_implicit}) ===')
for d, rv, e, c, common in sorted(implicit, reverse=True):
    print(f'{d:>3}% revs={rv:<3} {e}  <->  {c}')
    if common != '—':
        print(f'         общий контракт: {common}')
