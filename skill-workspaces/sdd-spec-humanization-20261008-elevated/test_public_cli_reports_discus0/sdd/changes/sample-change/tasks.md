---
schema_version: 1
document_type: tasks
change_id: sample-change
language: ru
---
# План реализации

### Реализовать и проверить результат

```yaml
sdd_record: task
id: TASK-sample-result
number: 1
covers: [AC-sample-result]
depends_on: []
cannot_parallel_with: []
status: pending
verification:
  - criteria: [AC-sample-result]
    test_description: Проверьте наблюдаемый результат в указанных условиях
    location: tests/test_sample.py
    run:
      setup_required: В этой задаче настройте проектную команду и выполните указанный тест
```

Опишите реализацию и необходимые тесты, включая интеграционные. Назначьте каждый AC ровно одной задаче; следующие задачи могут использовать результат через depends_on. Общие файлы требуют оценки совместимости: распределите разделы либо задайте cannot_parallel_with. Номера — отображение, ссылки — стабильные ID.
