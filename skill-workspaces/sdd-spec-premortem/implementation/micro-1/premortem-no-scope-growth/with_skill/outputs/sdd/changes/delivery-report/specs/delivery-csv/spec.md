---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-csv
---
# Состав CSV

Частичный черновик по [docs/report.md](../../../../../docs/report.md). Определяет состав колонок, общий для вариантов с автоматическим назначением и без него.

## Три согласованные колонки

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV отчёта должен содержать ровно три колонки: delivery_id, overdue_minutes, responsible. Это требование не задаёт способ выбора исполнителя и не разрешает изменение назначений.

### Проверка состава

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Сформирован CSV ежедневного отчёта доставки.
expected: CSV содержит ровно три колонки с именами delivery_id, overdue_minutes, responsible.
```

## Границы черновика

Типы значений, обязательность responsible, отбор строк, порядок колонок, кодировка, разделитель, экранирование и обработка ошибок не определены источником. Новых требований к ним этот черновик не вводит. Ближайший вопрос — [Q-report-action](../../state.md#ближайший-вопрос); затем уточняется контракт данных.