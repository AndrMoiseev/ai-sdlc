---
schema_version: 1
document_type: spec
change_id: sample-change
language: ru
capability: refunds
---
# refunds
```yaml
sdd_record: requirement
id: REQ-refunds
operation: add
```
Прежний Payment Service принимает RefundRequested с ключом и подтверждает возврат; retry endpoint отвечает 410; текст подтверждения меняется.
```yaml
sdd_record: acceptance
id: AC-refund
requirement: REQ-refunds
conditions: Запрошен возврат
expected: Payment Service подтверждает возврат с ключом
```
```yaml
sdd_record: acceptance
id: AC-retired
requirement: REQ-refunds
conditions: Вызван retry endpoint
expected: HTTP 410 без вызова Payment Service
```
```yaml
sdd_record: acceptance
id: AC-wording
requirement: REQ-refunds
conditions: Возврат подтвержден
expected: Текст: Возврат принят
```

