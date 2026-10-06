---
schema_version: 1
document_type: decisions
change_id: sdd-spec-premortem
language: ru
---
# Решения пользователя

### Отказ от ревью документов

```yaml
sdd_record: user
id: USER-skip-premortem-document-review
kind: review_waiver
scope:
  stage: document_review
  lenses: [consistency]
response: 'нет, давай сразу план'
date: '2026-10-06T11:44:07Z'
inputs:
  - path: design.md
    sha256: 43cc10315d31f39bc1d480a7d55a9f54572ec1706d04f7c7dc477626361ce9e2
  - path: proposal.md
    sha256: 1cb79960a83a87e0dc2b13c7f71ba9fcc174e86c82e90959ad9c5bf97d236c6b
  - path: specs/premortem/spec.md
    sha256: 58cdfceea7dbc1d30065b0b20a2481abb09706478641690baf0d66f501d2b7fe
status: active
```

### Текущие документы как основание плана

```yaml
sdd_record: user
id: USER-accept-premortem-documents
kind: document_approval
scope:
  stage: document_review
response: 'нет, давай сразу план'
date: '2026-10-06T11:44:07Z'
inputs:
  - path: design.md
    sha256: 43cc10315d31f39bc1d480a7d55a9f54572ec1706d04f7c7dc477626361ce9e2
  - path: proposal.md
    sha256: 1cb79960a83a87e0dc2b13c7f71ba9fcc174e86c82e90959ad9c5bf97d236c6b
  - path: specs/premortem/spec.md
    sha256: 58cdfceea7dbc1d30065b0b20a2481abb09706478641690baf0d66f501d2b7fe
status: active
```

### Подготовка плана

```yaml
sdd_record: user
id: USER-plan-premortem
kind: planning_command
scope:
  stage: document_review
  work: Подготовить план реализации sdd-spec-premortem по текущим proposal, specs и design.
response: 'нет, давай сразу план'
date: '2026-10-06T11:44:07Z'
inputs:
  - path: design.md
    sha256: 43cc10315d31f39bc1d480a7d55a9f54572ec1706d04f7c7dc477626361ce9e2
  - path: proposal.md
    sha256: 1cb79960a83a87e0dc2b13c7f71ba9fcc174e86c82e90959ad9c5bf97d236c6b
  - path: specs/premortem/spec.md
    sha256: 58cdfceea7dbc1d30065b0b20a2481abb09706478641690baf0d66f501d2b7fe
status: completed
```
