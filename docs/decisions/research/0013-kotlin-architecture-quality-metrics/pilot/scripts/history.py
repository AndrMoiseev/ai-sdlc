#!/usr/bin/env python3
"""Исторические сигналы из metrics/git.log — замена code-maat без java-зависимости.

Семантика воспроизводит code-maat 1.0.4 (проверено сравнением выводов на одном
git.log; см. «Известные пробелы» в README — ренеймы git вида path/{old => new}
не нормализуются, как и в code-maat):

  revisions     n-revs по всем коммитам, сортировка по убыванию;
  entity-churn  добавлено/удалено строк на сущность; бинарники ('-') = 0;
                сортировка по добавленному убыванием;
  summary       коммиты / сущности / строк изменений / авторы;
  coupling      пары сущностей, менявшихся вместе в коммитах размером
                <= 30 файлов; degree = int(shared / ((revs(A)+revs(B))/2) * 100);
                пороги: средние ревизии пары >= 5, общие >= 5, degree >= 30;
                average-revs = ceil(среднего); сортировка (degree, average-revs)
                убыванием.

Обобщённо: вход — любой git-лог формата `--<rev>--<date>--<author>` + numstat.
Запуск: python3 metrics/history.py (git.log уже экспортирован, см. Makefile).
"""
import csv
import math
import re
from collections import Counter
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория

MIN_REVS, MIN_SHARED, MIN_COUPLING = 5, 5, 30
MAX_COUPLING, MAX_CHANGESET = 100, 30
HDR = re.compile(r'^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.+)$')

changesets = []  # коммит -> строки-сущности (как в логе)
churn = {}
authors = set()
entities = set()
n_rows = 0
cur = None
for line in open(DATA / 'git.log'):
    m = HDR.match(line.strip())
    if m:
        authors.add(m.group(3))
        cur = []
        changesets.append(cur)
        continue
    parts = line.rstrip('\n').split('\t')
    if len(parts) == 3 and cur is not None:
        added, deleted, entity = parts
        cur.append(entity)
        n_rows += 1
        entities.add(entity)
        c = churn.setdefault(entity, [0, 0, 0])
        c[0] += 0 if added == '-' else int(added)
        c[1] += 0 if deleted == '-' else int(deleted)
        c[2] += 1

if not changesets:
    raise SystemExit('git.log пуст или не распознан')


def write(name, header, rows) -> None:
    with open(DATA / name, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# --- revisions: n-revs по всем коммитам ---
n_revs = Counter(e for cs in changesets for e in cs)
write('revisions.csv', ['entity', 'n-revs'],
      sorted(n_revs.items(), key=lambda x: (-x[1], x[0])))

# --- entity-churn ---
write('entity-churn.csv', ['entity', 'added', 'deleted', 'commits'],
      ((e, c[0], c[1], c[2]) for e, c in sorted(churn.items(), key=lambda x: (-x[1][0], x[0]))))

# --- summary ---
write('summary.csv', ['statistic', 'value'], [
    ('number-of-commits', len(changesets)),
    ('number-of-entities', len(entities)),
    ('number-of-entities-changed', n_rows),
    ('number-of-authors', len(authors)),
])

# --- coupling ---
module_revs: Counter = Counter()
pair_shared: Counter = Counter()
for cs in changesets:
    if len(cs) > MAX_CHANGESET:  # фильтр размера changeset — до построения пар
        continue
    uniq = sorted(set(cs))
    module_revs.update(uniq)
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            pair_shared[(uniq[i], uniq[j])] += 1

rows = []
for (a, b), shared in pair_shared.items():
    avg = (module_revs[a] + module_revs[b]) / 2
    degree = int(shared / avg * 100)
    if avg >= MIN_REVS and shared >= MIN_SHARED and MIN_COUPLING <= degree <= MAX_COUPLING:
        rows.append((degree, math.ceil(avg), a, b))
write('coupling.csv', ['entity', 'coupled', 'degree', 'average-revs'],
      [(a, b, d, r) for d, r, a, b in sorted(rows, key=lambda x: (-x[0], -x[1], x[2], x[3]))])

print(f'{len(changesets)} коммитов, {len(entities)} сущностей, {n_rows} строк изменений; '
      f'coupling-пар >= порогов: {len(rows)}')
