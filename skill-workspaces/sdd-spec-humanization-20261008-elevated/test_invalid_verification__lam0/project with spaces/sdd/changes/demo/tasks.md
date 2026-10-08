---
change_id: demo
document_type: tasks
language: en
schema_version: 1
---

### Record

```yaml
sdd_record: task
id: TASK-feature
number: 1
covers:
- AC-feature
depends_on: []
status: pending
verification:
- criteria: []
  test_description: Check output
  location: tests/future.py
  run:
    command: pytest tests/future.py
```

Description.

