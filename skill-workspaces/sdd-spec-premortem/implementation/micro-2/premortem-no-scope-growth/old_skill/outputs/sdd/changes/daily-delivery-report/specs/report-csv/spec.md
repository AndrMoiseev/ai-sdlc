---
schema_version: 1
document_type: spec
change_id: daily-delivery-report
language: ru
capability: report-csv
---
# CSV ежедневного отчёта — частичный черновик

Источник: [docs/report.md](../../../../../docs/report.md). Три колонки согласованы для обоих вариантов. Ниже описана только независимая часть контракта.

## Состав колонок

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV отчёта содержит ровно три колонки: `delivery_id`, `overdue_minutes`, `responsible`.

### Проверка состава

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Сформирован CSV ежедневного отчёта доставки.
expected: CSV содержит ровно три колонки с именами delivery_id, overdue_minutes и responsible.
```

Критерий проверяет состав, а не источник назначения исполнителя. Значение `responsible` само по себе не означает автоматического назначения.

### Границы черновика

Порядок колонок, кодировка, разделитель, типы и пустые значения, правила отбора доставок и расчёта просрочки ещё не установлены. Этот документ не задаёт их по умолчанию. В проекте нет данных доставок; фактический CSV с записями не создавался.
