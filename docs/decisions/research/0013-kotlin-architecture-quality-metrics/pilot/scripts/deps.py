#!/usr/bin/env python3
"""Статический граф зависимостей из байткода (jdeps) и производные графы.

Обобщённо: на входе любой вывод jdeps -verbose:class. Стек-специфика этого
проекта — фильтр сгенерированного (composition root Kora, OpenAPI) и
корзина legacy (всё вне объявленных контекстов из _buckets.CONTEXTS).

Запуск (нужна скомпилированная сборка, обычной компиляции достаточно):
  python3 metrics/deps.py

Выход в metrics/:
  deps-class.csv — рёбра класс→класс (hand-written, сгенерированное отфильтровано)
  deps-pkg.csv   — пакет→пакет, вес = число рёбер между классами пакетов
  deps-ctx.csv   — контекст→контекст, вне контекстов = legacy, вес = число рёбер

Сырой вывод jdeps не храним (мегабайты, восстанавливается перезапуском).
"""
import collections
import csv
import re
import subprocess
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория
ROOT = M.parent.parent
CLASSES = ROOT / 'app/build/classes/kotlin/main'
P = 'ru.tbank.gp.matcher.'

CONTEXTS = {
    'brand', 'catalog', 'categorization', 'matching', 'offline', 'orchestration',
    'settings', 'groupidReconcile', 'deduplication', 'tsku',
}
# Сгенерированное: composition root Kora и OpenAPI-кодогенерация.
GEN_ROOT = {'Application', 'ApplicationImpl', 'ApplicationGraph', 'ApplicationSubmoduleImpl'}

if not CLASSES.is_dir():
    raise SystemExit(f'нет {CLASSES} — прогоните сборку (./gradlew compileKotlin)')

raw = subprocess.run(
    ['jdeps', '-verbose:class', '--ignore-missing-deps', str(CLASSES)],
    capture_output=True, text=True, check=True,
).stdout

edges = set()
# Колонки jdeps выровнены по ширине: пробелов вокруг '->' может быть много.
for m in re.finditer(r'^\s+(\S+)\s+->\s+(\S+)', raw, re.M):
    a, b = m.group(1), m.group(2)
    if not (a.startswith(P) and b.startswith(P)):
        continue
    a, b = a.split('$')[0], b.split('$')[0]
    if a.rsplit('.', 1)[-1] in GEN_ROOT or b.rsplit('.', 1)[-1] in GEN_ROOT:
        continue
    if '.generated.' in a or '.generated.' in b:
        continue
    if a == b:
        continue
    edges.add((a, b))

with open(DATA / 'deps-class.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['from', 'to'])
    w.writerows(sorted(edges))


def key_pkg(c: str) -> str:
    return c[: c.rfind('.')]


def key_ctx(c: str) -> str:
    first = c[len(P):].split('.')[0]
    return first if first in CONTEXTS else 'legacy'


def aggregate(key) -> tuple[dict, int]:
    cross: collections.Counter = collections.Counter()
    intra = collections.Counter()
    for a, b in edges:
        ka, kb = key(a), key(b)
        (intra if ka == kb else cross)[(ka, kb)] += 1
    return cross, intra


def write_csv(path: Path, counter) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['from', 'to', 'weight'])
        for (a, b), n in sorted(counter.items(), key=lambda x: -x[1]):
            w.writerow([a, b, n])


pkg_cross, pkg_intra = aggregate(key_pkg)
ctx_cross, ctx_intra = aggregate(key_ctx)
write_csv(DATA / 'deps-pkg.csv', pkg_cross)
write_csv(DATA / 'deps-ctx.csv', ctx_cross)

print(f'рёбер класс→класс: {len(edges)}; пакетных пар: {len(pkg_cross)}; контекстных пар: {len(ctx_cross)}')
print('\n=== Контекстный граф (вес = рёбер классов) ===')
for (a, b), n in ctx_cross.most_common():
    print(f'{n:>5}  {a:>15} -> {b}')
print('\n=== Внутренние рёбра ===')
for k, n in ctx_intra.most_common():
    print(f'{n:>5}  внутри {k}')
print('\n=== Топ-25 пакетных рёбер ===')
for (a, b), n in pkg_cross.most_common(25):
    print(f'{n:>4}  {a[len(P):]} -> {b[len(P):]}')
