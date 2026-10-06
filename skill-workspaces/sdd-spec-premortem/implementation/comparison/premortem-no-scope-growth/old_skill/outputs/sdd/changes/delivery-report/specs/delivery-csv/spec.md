---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-csv
---
# CSV отчёта о доставках

Источник: [docs/report.md](../../../../../docs/report.md).
Три колонки согласованы для обоих обсуждаемых вариантов.
Ниже описана только независимая часть контракта; полный формат данных ещё не определён.

## Состав колонок

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV содержит ровно три колонки в указанной в источнике последовательности:
delivery_id, overdue_minutes, responsible.

### Проверка заголовка

```yaml
sdd_record: acceptance
id: AC-csv-header
requirement: REQ-csv-columns
conditions: Сформирован CSV ежедневного отчёта.
expected: Заголовок содержит ровно delivery_id, overdue_minutes, responsible в этом порядке.
```

Образец заголовка сохранён в [sample-header.csv](../../sample-header.csv).
Он не содержит вымышленных доставок и не является готовым ежедневным отчётом.
