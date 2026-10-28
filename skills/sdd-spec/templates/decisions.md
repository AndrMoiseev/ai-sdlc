---
schema_version: 2
document_type: decisions
work_kind: change
change_id: sample-change
language: ru
---
# Решения пользователя

Записывайте только фактические явные ответы. Не копируйте пример как состоявшееся согласование. Каждая реальная USER-запись начинается с заголовка ### и YAML-блока. Поля и варианты scope: [формат ревью и согласований](../../sdd-shared/references/document-format-review.md#user-решения-и-область-разрешения).

````markdown
### Команда подготовки плана

```yaml
sdd_record: user
id: USER-plan-request
work_kind: change
change_id: sample-change
kind: planning_command
scope:
  stage: document_review
  work: Подготовить план согласованного sample-change
response: Точный ответ пользователя
date: '2026-01-01T00:00:00Z'
basis_commit: <полный OID существующего коммита>
status: active
```
````

Замените basis_commit реальным полным OID исходного коммита. Поручение сохраняется в своей области до выполнения, отмены или замены. Отмену отразите status: cancelled с источником ответа; новая запись при замене содержит supersedes. Для принятия состояния используйте kind: state_acceptance, scope: {}, accepted_commit вместо basis_commit и обязательный message с источником ответа. Принятие не является поручением; запись входит в следующий обычный checkpoint.
