---
schema_version: 1
document_type: design
change_id: sample-change
language: ru
---

# Дизайн
Обработчик orders сохраняет связь Idempotency-Key с order_id и возвращает существующую запись при повторе. Обработчик retry становится 410 tombstone. Тестовая инфраструктура отсутствует; подготовить локальный запуск внутри задач. Новых вопросов нет.

### DEC-preserve-key-map

```yaml
sdd_record: decision
id: DEC-preserve-key-map
requirements:
- REQ-reuse-order
```
