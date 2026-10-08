---
schema_version: 1
document_type: decisions
change_id: sample-change
language: ru
---

### Согласование

```yaml
date: '2026-01-01T01:00:00Z'
id: USER-approve-plan
inputs:
- path: design.md
  sha256: 2f34cda87c62e20d18d00292c89a67239c168d14759e57cdd20ddfac8845f4b0
- path: proposal.md
  sha256: 742a700e5f58b79bed894d2f24427bcb394170f52a639f0920cf7cd5f8689399
- path: specs/sample-capability/spec.md
  sha256: 756ee7a48946d37c8734761f5f45dfc2ef874fbf12b321a4e81e110c82974df2
- path: specs/second-capability/spec.md
  sha256: 6fdd2dad4ea682aceb1264d29edd5e5f05068fbae3e87817e824db5c016d97e1
- path: tasks.md
  sha256: 256f8ff43fab26308d8064fb4800aead02903dee540be33b6dafac25394c895d
kind: plan_approval
response: Согласован именно этот комплект
scope:
  stage: plan_review
sdd_record: user
```
