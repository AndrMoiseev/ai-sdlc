---
document_type: decisions
schema_version: 1
---

### Record

```yaml
sdd_record: user
id: USER-document-approval
kind: document_approval
scope:
  stage: document_review
response: Explicit instruction
date: '2026-01-01T01:00:00Z'
inputs:
- path: design.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: proposal.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: specs/example/spec.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
```

### Record

```yaml
sdd_record: user
id: USER-review-waiver
kind: review_waiver
scope:
  stage: document_review
  lenses:
  - consistency
response: Explicit instruction
date: '2026-01-01T01:00:00Z'
inputs:
- path: design.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: proposal.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: specs/example/spec.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
```
