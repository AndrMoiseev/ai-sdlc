---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: report-csv
---
# Контракт CSV — частичный черновик

Основание: [docs/report.md](../../../../../docs/report.md). Состав колонок согласован для обоих вариантов; остальные параметры этим документом не утверждаются.

## Три колонки отчёта

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV содержит три колонки: delivery_id, overdue_minutes, responsible.

### Проверка состава

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Получен CSV ежедневного отчёта диспетчеру.
expected: CSV содержит ровно три колонки с именами delivery_id, overdue_minutes, responsible.
```

Проверка применима независимо от выбора автоматического назначения. Пример состава сохранён в [columns.csv](../../columns.csv); он не содержит фактических данных доставок и не является готовым ежедневным отчётом.

Типы и значения полей, отсутствие исполнителя, правила выборки, расчёт просрочки и параметры сериализации ещё не определены. Они не считаются согласованными.
