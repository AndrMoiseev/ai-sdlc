---
schema_version: 1
document_type: spec
change_id: sample-change
language: ru
capability: orders
---
# orders
```yaml
sdd_record: requirement
id: REQ-orders
operation: add
```
API возвращает прежний заказ при повторе ключа; новый worker принимает асинхронное сообщение создания; отказ оплаты завершает процесс.
```yaml
sdd_record: acceptance
id: AC-repeat
requirement: REQ-orders
conditions: Повтор использованного ключа
expected: Прежний заказ без второй записи
```
```yaml
sdd_record: acceptance
id: AC-async
requirement: REQ-orders
conditions: Заказ создан
expected: Worker получает асинхронное OrderCreated
```
```yaml
sdd_record: acceptance
id: AC-decline
requirement: REQ-orders
conditions: Платеж отклонен
expected: Процесс завершается без нового заказа
```

