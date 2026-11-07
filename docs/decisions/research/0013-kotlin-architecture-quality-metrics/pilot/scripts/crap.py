#!/usr/bin/env python3
"""CRAP (Change Risk Anti-Pattern) по Савойе/Эвансу:

    CRAP = mcc^2 * (1 - coverage)^3 + mcc

mcc — сумма цикломатической сложности функций класса-файла (полный ряд из
metrics/detekt-metrics.sarif, порог 1), coverage — line-покрытие файла из
metrics/coverage-latest.csv. Порог беспокойства 30 — из первоисточника:
выше — кандидат на рефакторинг или тесты.

Уровни: класс-файл -> пакет (каталог) -> контекст (конфигурация корзин в
_buckets.py; плоские пакеты -> legacy). Выход в metrics/data/:
crap-class.csv, crap-pkg.csv, crap-ctx.csv (Σ/среднее/кол-во выше порога/Σ mcc).
Метрика обобщённая; входы — SARIF полного ряда + пофайловое покрытие.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория
sys.path.insert(0, str(M))
from _buckets import classify  # noqa: E402 — конфигурация корзин проекта

MCC = re.compile(r'Cyclomatic Complexity \(complexity: (\d+)\)')
CRAP_LIMIT = 30


def sarif_mcc_per_file() -> dict[str, int]:
    d = json.load(open(DATA / 'detekt-metrics.sarif'))
    per_file: dict[str, int] = defaultdict(int)
    for r in d['runs'][0]['results']:
        if not r['ruleId'].endswith('CyclomaticComplexMethod'):
            continue
        m = MCC.search(r['message']['text'])
        if not m:
            continue
        uri = r['locations'][0]['physicalLocation']['artifactLocation']['uri']
        path = uri.replace('file://', '')
        marker = '/gp-matcher/'
        if marker in path:
            path = path.split(marker, 1)[1]
        per_file[path] += int(m.group(1))
    return per_file


mcc = sarif_mcc_per_file()
cov = {r['file'].replace('file://', ''): float(r['line_pct'])
       for r in csv.DictReader(open(DATA / 'coverage-latest.csv'))}

rows = []  # (crap, path, cr, coverage)
no_cov = 0
for path, cr in mcc.items():
    c = cov.get(path)
    if c is None:
        no_cov += 1
        continue
    rows.append((cr ** 2 * (1 - c) ** 3 + cr, path, cr, c))
rows.sort(reverse=True)

with open(DATA / 'crap-class.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['file', 'mcc', 'line_coverage', 'crap'])
    w.writerows((path, cr, f'{c:.4f}', f'{crap:.1f}') for crap, path, cr, c in rows)

print(f'класс-файлов с mcc: {len(mcc)}; без покрытия (исключены): {no_cov}; '
      f'CRAP > {CRAP_LIMIT}: {sum(1 for x in rows if x[0] > CRAP_LIMIT)}')
print(f'\n=== Топ-15 класс-файлов по CRAP ===')
print(f'{"CRAP":>7} {"mcc":>4} {"line":>5}  файл')
for crap, path, cr, c in rows[:15]:
    print(f'{crap:>7.1f} {cr:>4} {c:>5.0%}  {path.replace("app/src/main/kotlin/ru/tbank/gp/matcher/", "")}')


def bucket(path: str) -> str:
    b = classify(path)
    return 'legacy' if b.startswith(('flat:', 'test-', 'res', 'infra')) else b


by_pkg: dict[str, list[float]] = defaultdict(list)
by_ctx: dict[str, list[float]] = defaultdict(list)
pkg_mcc: dict[str, int] = defaultdict(int)
ctx_mcc: dict[str, int] = defaultdict(int)
for crap, path, cr, c in rows:
    pkg = path.rsplit('/', 1)[0]
    ctx = bucket(path)
    by_pkg[pkg].append(crap)
    by_ctx[ctx].append(crap)
    pkg_mcc[pkg] += cr
    ctx_mcc[ctx] += cr


def write_agg(name: str, groups: dict[str, list[float]], mccs: dict[str, int], first: str) -> None:
    with open(DATA / name, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([first, 'files', 'sum_crap', 'mean_crap', 'crap_over_30', 'sum_mcc'])
        for g, vals in sorted(groups.items(), key=lambda x: -sum(x[1])):
            w.writerow([g, len(vals), f'{sum(vals):.1f}', f'{sum(vals) / len(vals):.1f}',
                        sum(1 for v in vals if v > CRAP_LIMIT), mccs[g]])


write_agg('crap-pkg.csv', by_pkg, pkg_mcc, 'package')
write_agg('crap-ctx.csv', by_ctx, ctx_mcc, 'context')

print(f'\n=== По контекстам (legacy = плоские пакеты) ===')
print(f'{"Σ CRAP":>8} {"средн.":>7} {">30":>4} {"файлов":>7}  контекст')
for ctx, vals in sorted(by_ctx.items(), key=lambda x: -sum(x[1])):
    print(f'{sum(vals):>8.0f} {sum(vals) / len(vals):>7.1f} '
          f'{sum(1 for v in vals if v > CRAP_LIMIT):>4} {len(vals):>7}  {ctx}')

print(f'\n=== Топ-10 пакетов по Σ CRAP ===')
for pkg, vals in sorted(by_pkg.items(), key=lambda x: -sum(x[1]))[:10]:
    print(f'{sum(vals):>8.0f} (средн. {sum(vals) / len(vals):>5.1f}, '
          f'{" ".join(pkg.replace("app/src/main/kotlin/ru/tbank/gp/matcher/", "").split("/")[-2:])})')
