---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-report
---
# Delivery report

Частичный черновик общего контракта. Источник: [docs/report.md](../../../../../docs/report.md). Открытые вопросы не отменяют согласованный состав CSV.

## Три колонки CSV

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

Отчёт для диспетчера доставки должен иметь формат CSV с ровно тремя колонками: delivery_id, overdue_minutes, responsible. Состав колонок одинаков для режима только отчёта и режима с автоматическим назначением исполнителей.

### Состав колонок не зависит от режима

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Сформирован отчёт в любом из двух рассматриваемых режимов.
expected: CSV содержит ровно три колонки — delivery_id, overdue_minutes, responsible; дополнительных колонок нет.
```

Проверка применяется к каждому режиму, который войдёт в выбранный объём. Этот критерий не требует реализовать оба режима.

## Границы черновика

В источнике зафиксирована ежедневная выдача в 09:00. Часовой пояс, способ доставки файла, выборка строк, расчёт overdue_minutes, представление responsible и ошибки не описаны. Это пробелы контракта, а не свобода реализации; см. [Q-report-contract](../../state.md#детали-контракта).

Поведение автоматического назначения не специфицировано до [выбора режима](../../state.md#режим-работы).
