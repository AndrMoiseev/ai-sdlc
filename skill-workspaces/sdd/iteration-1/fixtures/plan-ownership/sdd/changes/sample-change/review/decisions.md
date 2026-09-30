---
schema_version: 1
document_type: decisions
change_id: sample-change
language: ru
---

# История синтетического сценария
Ниже явные ответы пользователя внутри fixture. Это не утверждение об ответах реального пользователя вне оценки.

### USER-documents

```yaml
sdd_record: user
id: USER-documents
kind: document_approval
scope:
  stage: document_review
response: Согласовываю текущие specs и design sample-change.
date: '2026-09-29T12:02:00Z'
inputs:
- path: design.md
  sha256: 07387ef2021244b2352a784ab385c31fbf80f1aee40342fbbc38efe3bc747a54
- path: proposal.md
  sha256: 689c954ce97e6feb16532c3cb73b5bcc77262de34778020b321ad2ce7e8134ac
- path: specs/orders/spec.md
  sha256: 7932783843def6d9e8e005c3ed540b6c650711d8fd50d3ea1dde13c9a74cddb0
status: active
```

### USER-plan

```yaml
sdd_record: user
id: USER-plan
kind: planning_command
scope:
  stage: document_review
  work: Подготовить только tasks.md для двух существующих AC sample-change
response: Создай только tasks.md для согласованного sample-change; реализацию не начинай.
date: '2026-09-29T12:02:00Z'
inputs:
- path: design.md
  sha256: 07387ef2021244b2352a784ab385c31fbf80f1aee40342fbbc38efe3bc747a54
- path: proposal.md
  sha256: 689c954ce97e6feb16532c3cb73b5bcc77262de34778020b321ad2ce7e8134ac
- path: specs/orders/spec.md
  sha256: 7932783843def6d9e8e005c3ed540b6c650711d8fd50d3ea1dde13c9a74cddb0
status: active
```
