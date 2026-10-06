---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-report
---
# Отчёт о доставках

Источник: [docs/report.md](../../../../../docs/report.md). Черновик описывает общую часть обоих вариантов. Правила автоматического назначения не определены.

## Ежедневный отчёт диспетчеру

```yaml
sdd_record: requirement
id: REQ-daily-report
operation: add
```

Система должна ежедневно предоставлять диспетчеру доставки отчёт в 09:00. Часовой пояс и способ предоставления требуют уточнения в Q-report-contract; часовой пояс среды агента не считается часовым поясом продукта.

### Время и получатель

```yaml
sdd_record: acceptance
id: AC-daily-report
requirement: REQ-daily-report
conditions: Наступило 09:00 очередного дня в часовом поясе продукта, который предстоит согласовать.
expected: Диспетчеру доставки предоставлен ежедневный отчёт согласованным способом.
```

Этот критерий частичный: до уточнения часового пояса и канала его нельзя использовать для окончательной приёмки.

## Три колонки CSV

```yaml
sdd_record: requirement
id: REQ-report-csv
operation: add
```

Отчёт должен иметь формат CSV ровно с тремя колонками в согласованном порядке: `delivery_id`, `overdue_minutes`, `responsible`. Состав колонок не зависит от выбора между только отчётом и автоматическим назначением исполнителей. Дополнительная колонка для режима или результата назначения не предусмотрена.

### Состав и порядок колонок

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-report-csv
conditions: Сформирован CSV-отчёт о доставках.
expected: CSV содержит ровно три колонки в порядке delivery_id, overdue_minutes, responsible.
```

### Независимость от режима

```yaml
sdd_record: acceptance
id: AC-csv-mode-independent
requirement: REQ-report-csv
conditions: При дальнейшей проработке выбран любой из двух обсуждаемых режимов.
expected: Состав и порядок колонок CSV остаются delivery_id, overdue_minutes, responsible.
```

Критерий не требует поддержки переключения режимов: продуктовый выбор ещё не сделан. Правила отбора строк, расчёта просрочки, значения responsible и обработки ошибок остаются открытыми в Q-report-contract.
