---
schema_version: 1
document_type: "spec"
change_id: "delivery-report"
language: "ru"
capability: "main"
---
# Наблюдаемое поведение

## REQ-report-export

```yaml
sdd_record: requirement
id: REQ-report-export
operation: add
```

Ежедневно до назначения исполнителей в 07:30 диспетчер получает CSV с просроченными доставками. Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер.

### Критерий приемки

```yaml
sdd_record: "acceptance"
id: "AC-report-delivered"
requirement: "REQ-report-export"
conditions: "Наступил срок ежедневного отчёта; имеются просроченные доставки"
expected: "Диспетчеру доступен CSV до назначения исполнителей в 07:30 с колонками delivery_id, overdue_minutes, responsible"
```

Точный срок в REQ-report-export и AC-report-delivered нужно уточнить после ответа на [Q-report-time](../../state.md#время-отчёта). 07:30 — время назначения, а не выбранный срок отчёта. Критерий остаётся черновым; прежние 08:00 устарели.