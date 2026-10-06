---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-csv
---
# CSV отчёта доставки

Этот черновик фиксирует только состав колонок из [исходного описания](../../../../../docs/report.md). Он не определяет автоматическое назначение и не подтверждает полезность отчёта.

## Состав колонок

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV содержит три колонки: `delivery_id`, `overdue_minutes`, `responsible`. Это общая часть обоих рассматриваемых вариантов.

### Три согласованные колонки

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Сформирован CSV отчёта доставки в любом из рассматриваемых вариантов поведения.
expected: Набор колонок состоит ровно из delivery_id, overdue_minutes и responsible.
```

[Пример заголовка](../../csv-header.csv) демонстрирует согласованные имена. Он не содержит реальных доставок и не доказывает работу экспорта. Порядок колонок, наличие строки заголовка и параметры сериализации показаны как пример, а не как дополнительные согласованные обязательства.
