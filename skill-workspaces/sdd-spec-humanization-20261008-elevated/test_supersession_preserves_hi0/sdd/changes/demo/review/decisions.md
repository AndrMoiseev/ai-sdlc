---
document_type: decisions
schema_version: 1
---

### Record

```yaml
sdd_record: user
id: USER-planning-command
kind: planning_command
scope:
  stage: document_review
  work: Original scope
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
id: USER-replacement
kind: planning_command
scope:
  stage: document_review
  work: Original scope
response: Explicit instruction
date: '2026-01-02T01:00:00Z'
inputs:
- path: design.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: proposal.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
- path: specs/example/spec.md
  sha256: da222f9a966952e39a27e90cdb3f7c30964c8535de5d1a59b8f2c26dda057813
supersedes:
- USER-planning-command
status: cancelled
```
