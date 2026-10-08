---
schema_version: 1
document_type: spec
change_id: sample-change
language: ru
capability: sample-capability
---
# Capability

## Наблюдаемое поведение

```yaml
sdd_record: requirement
id: REQ-sample-behavior
operation: add
```

Запишите полное предлагаемое поведение затронутого требования, включая ошибки и ограничения.

Для modify/remove добавьте source по references/document-format.md. Удаление тоже имеет критерии результата. Сценарии с SCN-ID не нужны.

### Критерий приемки

```yaml
sdd_record: acceptance
id: AC-sample-result
requirement: REQ-sample-behavior
conditions: Условия и действие, вызывающее поведение
expected: Наблюдаемый результат
```

Разместите остальные критерии этого требования под заголовками `###`, затем начните следующее требование с `##`.
