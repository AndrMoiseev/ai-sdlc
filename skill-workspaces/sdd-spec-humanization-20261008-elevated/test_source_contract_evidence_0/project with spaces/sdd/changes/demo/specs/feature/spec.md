---
capability: feature
change_id: demo
document_type: spec
language: en
schema_version: 1
---

### Record

```yaml
sdd_record: requirement
id: REQ-feature
operation: modify
source:
  kind: evidence
  baseline_missing: true
  references:
  - baseline.md
  observed: Original behavior
  assumptions: No additional assumptions
```

Description.

### Record

```yaml
sdd_record: acceptance
id: AC-feature
requirement: REQ-feature
conditions: Input
expected: Output
```

Description.

