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

Ежедневно к 07:00 диспетчер получает CSV с просроченными доставками. Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер.

### Критерий приемки

```yaml
sdd_record: "acceptance"
id: "AC-report-delivered"
requirement: "REQ-report-export"
conditions: "Наступил срок ежедневного отчёта; имеются просроченные доставки"
expected: "Диспетчеру доступен CSV к 07:00 с колонками delivery_id, overdue_minutes, responsible"
```
