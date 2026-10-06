---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-csv
---
# CSV ежедневного отчёта

Черновик по [исходному описанию](../../../../../docs/report.md).

## Согласованный состав колонок

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV содержит три колонки: delivery_id, overdue_minutes, responsible.
Состав одинаков для обоих обсуждаемых вариантов назначения.
[Пример заголовка](../../report-header.csv) следует порядку перечисления в источнике.
Формат значений и правила отбора строк пока не определены.

### Проверка состава

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Проверяется заголовок CSV ежедневного отчёта.
expected: Заголовок содержит ровно delivery_id, overdue_minutes и responsible, каждую колонку один раз.
```

### Независимость от назначения

```yaml
sdd_record: acceptance
id: AC-csv-independent
requirement: REQ-csv-columns
conditions: Сравниваются колонки для вариантов с автоматическим назначением и без него.
expected: В обоих вариантах сохраняются те же три колонки.
```