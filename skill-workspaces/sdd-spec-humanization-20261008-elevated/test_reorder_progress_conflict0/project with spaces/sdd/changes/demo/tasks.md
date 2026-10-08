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
number: 2
covers:
- AC-feature
depends_on:
- TASK-other
status: done
verification:
- criteria:
  - AC-feature
  test_description: Check output
  location: tests/future.py
  run:
    command: pytest tests/future.py
cannot_parallel_with:
- TASK-other
```

Description.

### Record

```yaml
sdd_record: task
id: TASK-other
number: 1
covers:
- AC-other
depends_on:
- TASK-feature
status: pending
verification:
- criteria:
  - AC-other
  test_description: Check output
  location: tests/future.py
  run:
    command: pytest tests/future.py
```

Description.

