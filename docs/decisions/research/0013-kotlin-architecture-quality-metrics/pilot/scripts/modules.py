#!/usr/bin/env python3
"""Обобщённые метрики модулей над графом зависимостей + объявленным разбиением.

Метрики от проекта не зависят; проектная специфика — только конфигурация
разбиения (набор объявленных модулей в _buckets.CONTEXTS).

Виды (все по пакетному графу metrics/deps-pkg.csv):
  1. Сплочённость модуля: внутренние рёбра / (внутренние + пересекающие
     границу). Низкая сплочённость при заметной внешней связанности —
     модуль не единица, а куча.
  2. Сродство узла с модулями (declared vs actual): доля внешнего веса
     узла в каждый модуль; классификация — согласован / смещён / сирота /
     мост — по порогам (константы ниже).
  3. I / A / D по Мартину: Instability = fan-out/(fan-in+fan-out) по
     внешним рёбрам; Abstractness = доля интерфейсов и abstract-классов
     в пакете (эвристика по исходникам); D = |A + I − 1|, «зона боли» —
     стабильный и конкретный.
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория
ROOT = M.parent.parent
SRC = ROOT / 'app/src/main/kotlin'
sys.path.insert(0, str(M))
from _buckets import CONTEXTS  # noqa: E402 — конфигурация объявленных модулей

P = 'ru.tbank.gp.matcher.'
DOMINANT, ORPHAN, BRIDGE, GRAY = 0.5, 0.25, 0.33, 0.34  # пороги сродства


def group_of(pkg: str) -> str:
    """Пакет -> объявленный модуль; вне объявленных — 'unassigned'."""
    first = pkg[len(P):].split('.')[0] if pkg.startswith(P) else pkg.split('.')[0]
    return 'ctx:' + first if first in CONTEXTS else 'unassigned'


def load_pkg_edges() -> dict[tuple[str, str], int]:
    edges: dict[tuple[str, str], int] = {}
    with open(DATA / 'deps-pkg.csv', newline='') as f:
        for r in csv.DictReader(f):
            edges[(r['from'], r['to'])] = int(r['weight'])
    return edges


edges = load_pkg_edges()

# --- 1. Сплочённость объявленных модулей ---
internal_w: Counter = Counter()
cross_w: Counter = Counter()
for (a, b), w in edges.items():
    ga, gb = group_of(a), group_of(b)
    if ga == gb:
        internal_w[ga] += w
    else:
        cross_w[ga] += w
        cross_w[gb] += w

print('=== Сплочённость модулей (внутренние рёбра / все) ===')
print(f'{"сплоч.":>7} {"внутр.":>7} {"гран.":>6}  модуль')
for g in sorted(internal_w, key=lambda x: internal_w[x] + cross_w[x], reverse=True):
    tot = internal_w[g] + cross_w[g]
    print(f'{internal_w[g] / tot:>7.0%} {internal_w[g]:>7} {cross_w[g]:>6}  {g}')

# --- 2. Сродство узлов с модулями (declared vs actual) ---
aff: dict[str, Counter] = defaultdict(Counter)
for (a, b), w in edges.items():
    ga, gb = group_of(a), group_of(b)
    if ga != gb:
        aff[a][gb] += w
        aff[b][ga] += w

cls: dict[str, tuple[str, str, float]] = {}  # pkg -> (класс, модуль, доля)
for n, counter in aff.items():
    total = sum(counter.values())
    declared = Counter({g: w for g, w in counter.items() if g != 'unassigned'})
    dtot = sum(declared.values())
    # Необъявленная масса — не модуль: если она забирает большую часть связи,
    # узел в «серой зоне» — сродство к объявленным модулям неопределимо.
    if dtot == 0 or dtot / total < GRAY:
        cls[n] = ('серая зона', '', dtot / total if dtot else 0.0)
        continue
    top_g, top_w = declared.most_common(1)[0]
    second_w = declared.most_common(2)[1][1] if len(declared) > 1 else 0
    share = top_w / dtot
    if share < ORPHAN:
        kind = 'сирота'
    elif second_w / dtot >= BRIDGE:
        kind = 'мост'
    else:
        kind = 'к ' + top_g
    cls[n] = (kind, top_g, share)

kinds = Counter(k for k, _, _ in cls.values())
print('\n=== Сродство пакетов с модулями (доминирование ≥50%, мост ≥33%, сирота <25%,'
      f' серая зона: <{GRAY:.0%} связи к объявленным) ===')
print('классификация всех пакетов с внешними рёбрами:', dict(kinds))

misplaced = [(n, g, s) for n, (k, g, s) in cls.items()
             if k.startswith('к ') and group_of(n) != 'unassigned' and k[2:] != group_of(n)]
print(f'смещённых (доминирует чужой модуль): {len(misplaced)}')
for n, g, s in sorted(misplaced, key=lambda x: -x[2])[:8]:
    print(f'  {s:>5.0%}  {n[len(P):]} тянется к {g} (объявлен в {group_of(n)})')

unassigned = [(sum(aff[n].values()), n, g, s) for n, (k, g, s) in cls.items()
              if group_of(n) == 'unassigned' and k.startswith('к ')]
print(f'\nвне объявленных модулей: с выраженной доминантой {len(unassigned)} пакетов:')
for tot, n, g, s in sorted(unassigned, reverse=True)[:12]:
    print(f'  {s:>5.0%}  {n[len(P):]} -> {g}')

# --- 3. I / A / D по Мартину ---
fan_in, fan_out = Counter(), Counter()
for (a, b), w in edges.items():
    fan_out[a] += w
    fan_in[b] += w

DECL = re.compile(
    r'^(?:@[\w.]+(?:\([^)]*\))?\s+)*'
    r'(?:(?:public|private|internal|protected)\s+)*'
    r'((?:(?:open|final|sealed|fun|data|value|enum|annotation|abstract|override|'
    r'companion|inline|external)\s+)*)(interface|class|object)\b')
types: Counter = Counter()
abstracts: Counter = Counter()
pkg_line = re.compile(r'^package\s+([\w.]+)')
for path in SRC.rglob('*.kt'):
    if '/build/' in str(path):
        continue
    pkg = None
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        m = pkg_line.match(line)
        if m:
            pkg = m.group(1)
            continue
        d = DECL.match(line.strip())
        if d and pkg:
            types[pkg] += 1
            if 'interface' == d.group(2) or 'abstract' in d.group(1):
                abstracts[pkg] += 1

print('\n=== I / A / D по Мартину (пакеты с ≥5 типами) ===')
print(f'{"I":>5} {"A":>5} {"D":>5}  пакет (зона боли: D высокий при I низком)')
rows = []
for pkg, n_types in types.items():
    if n_types < 5 or fan_in[pkg] + fan_out[pkg] == 0:
        continue
    i_ = fan_out[pkg] / (fan_in[pkg] + fan_out[pkg])
    a_ = abstracts[pkg] / n_types
    rows.append((abs(a_ + i_ - 1), i_, a_, pkg))
for d_, i_, a_, pkg in sorted(rows, reverse=True)[:15]:
    zone = ''
    if d_ >= 0.7 and i_ <= 0.3:
        zone = '  <== зона боли'
    elif d_ >= 0.7 and i_ >= 0.7:
        zone = '  <== зона бесполезности'
    print(f'{i_:>5.2f} {a_:>5.2f} {d_:>5.2f}  {pkg[len(P):] if pkg.startswith(P) else pkg}{zone}')
