---
schema_version: 1
document_type: spec
change_id: demo
language: en
capability: feature
---
# Fixture

## Feature

```yaml
sdd_record: requirement
id: REQ-feature
operation: add
```

Provide the feature.

### Accept feature

```yaml
sdd_record: acceptance
id: AC-feature
requirement: REQ-feature
conditions: Input is provided
expected: Output is returned
```

Observe the output.
