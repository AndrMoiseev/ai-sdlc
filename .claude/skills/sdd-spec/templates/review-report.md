---
schema_version: 2
work_kind: change
document_type: review
change_id: sample-change
language: ru
run_id: 20260101T000000Z-example
stage: review
lens_id: consistency
result: incomplete
started_at: '2026-01-01T00:00:00Z'
finished_at: '2026-01-01T00:00:00Z'
reviewed_commit: null
limitations: ['Шаблон: замените метаданные реальными данными запуска']
---
# Отчет независимого ревью

Сохраните как review/<run-id>/<lens-id>.md, не перезаписывая прежние отчёты. Stage всегда review. В одном запуске весь текущий комплект читают consistency, simplicity, premortem и проектные линзы; при наличии задач добавляется plan. Simplicity выполняется один раз. Для нового запуска используйте новый run-id. Укажите полный OID единого прочитанного коммита в reviewed_commit. Если основание не установлено, оставьте null и result: incomplete; не подставляйте текущий HEAD.

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
