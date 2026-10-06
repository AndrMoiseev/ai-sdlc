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

Ежедневно диспетчер получает CSV с просроченными доставками до назначения исполнителей в 07:30. Точное время готовности отчёта требует ответа на Q-report-time (см. state.md). Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер.

### Критерий приемки

```yaml
sdd_record: "acceptance"
id: "AC-report-delivered"
requirement: "REQ-report-export"
conditions: "Наступил срок ежедневного отчёта; имеются просроченные доставки"
expected: "До назначения исполнителей в 07:30 диспетчеру доступен CSV с колонками delivery_id, overdue_minutes, responsible; точный срок готовности ожидает ответа на Q-report-time"
```
