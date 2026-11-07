#!/usr/bin/env python3
"""Сохранение покрытия из jacoco XML в metrics/coverage-latest.csv.

Пофайловый снимок (перезаписывается): line/branch covered/total/pct.
Источник для секции E отчёта (metrics/report.py).

Запуск: python3 metrics/coverage.py (после ./gradlew :app:jacocoTestReport).
"""

import csv
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория
ROOT = M.parent.parent
JACOCO = ROOT / 'app/build/reports/jacoco/test/jacocoTestReport.xml'

if not JACOCO.exists():
    raise SystemExit(f'нет {JACOCO} — прогоните ./gradlew :app:jacocoTestReport')

commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip()

root = ET.parse(JACOCO).getroot()
files = []
line_cov = line_tot = br_cov = br_tot = 0
for pkg in root.findall('package'):
    for sf in pkg.findall('sourcefile'):
        c = {x.get('type'): (int(x.get('covered')), int(x.get('missed')) + int(x.get('covered')))
             for x in sf.findall('counter')}
        (lc, lt), (bc, bt) = c.get('LINE', (0, 0)), c.get('BRANCH', (0, 0))
        if lt == 0:
            continue
        path = f"app/src/main/kotlin/{pkg.get('name')}/{sf.get('name')}"
        files.append((path, lc, lt, f'{lc / lt:.4f}', bc, bt, f'{bc / bt:.4f}' if bt else ''))
        line_cov, line_tot, br_cov, br_tot = line_cov + lc, line_tot + lt, br_cov + bc, br_tot + bt

with open(DATA / 'coverage-latest.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['file', 'line_covered', 'line_total', 'line_pct',
                'branch_covered', 'branch_total', 'branch_pct'])
    w.writerows(files)

print(f'coverage (commit {commit}): {len(files)} файлов, '
      f'line {line_cov / line_tot:.0%}, branch {br_cov / br_tot:.0%} -> metrics/coverage-latest.csv')
