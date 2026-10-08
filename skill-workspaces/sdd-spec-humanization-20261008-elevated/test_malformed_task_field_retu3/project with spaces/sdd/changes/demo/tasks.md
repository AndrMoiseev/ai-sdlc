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
depends_on: null
status: pending
verification:
- criteria:
  - AC-feature
  test_description: Check output
  location: tests/future.py
  run:
    command: pytest tests/future.py
```

Description.

