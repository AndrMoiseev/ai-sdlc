---
schema_version: 1
document_type: spec
change_id: sample-change
language: ru
capability: orders
---

# Orders

### REQ-reuse-order

```yaml
sdd_record: requirement
id: REQ-reuse-order
operation: add
```

### AC-reuse-order

```yaml
sdd_record: acceptance
id: AC-reuse-order
requirement: REQ-reuse-order
conditions: POST /orders повторяет уже сохраненный Idempotency-Key с тем же запросом
expected: Возвращается прежний order_id; новый заказ не создается
```

### REQ-remove-retry

```yaml
sdd_record: requirement
id: REQ-remove-retry
operation: remove
source:
  kind: specification
  path: docs/orders.md
  requirement: Retry endpoint
```

### AC-retry-gone

```yaml
sdd_record: acceptance
id: AC-retry-gone
requirement: REQ-remove-retry
conditions: POST /orders/{id}/retry вызывается после удаления retry
expected: Ответ HTTP 410; повторное исполнение заказа не запускается
```
