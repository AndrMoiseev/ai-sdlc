---
schema_version: 1
document_type: review
change_id: sample-change
language: ru
run_id: 20260101T000000Z-example
stage: document_review
lens_id: consistency
result: incomplete
started_at: '2026-01-01T00:00:00Z'
finished_at: '2026-01-01T00:00:00Z'
inputs: []
inputs_after: []
freshness: stale
limitations: ['Шаблон: замените метаданные реальными данными запуска']
---
# Отчет независимого ревью

Сохраните как review/<run-id>/<lens-id>.md, не перезаписывая прежние отчеты. Для плана stage: plan_review, lens_id: plan. Вставьте полные манифесты snapshot до/после. Пустые списки inputs здесь — незаполненные поля шаблона, они не проходят check.

### Найденная проблема

```yaml
sdd_record: finding
id: FIND-sample-problem
source: REQ-sample-behavior
target:
  path: specs/sample-capability/spec.md
  element_id: REQ-sample-behavior
severity: recommendation
problem: Конкретная подтвержденная проблема
impact: Последствие для реализации или пользователя
suggestion: Предлагаемое исправление
```

Удалите пример при отсутствии находок. completed_no_findings требует отсутствия находок; completed_with_findings — хотя бы одну. incomplete указывает конкретное ограничение. Основной агент не дописывает находки за рецензента.
