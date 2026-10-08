---
schema_version: 1
document_type: decisions
change_id: sample-change
language: ru
---
# Решения пользователя

Записывайте только фактические явные ответы. Не копируйте пример как состоявшееся согласование. Каждая реальная USER-запись начинается с заголовка ### и YAML-блока. Поля и варианты scope: references/document-format.md.

````markdown
### Команда подготовки плана

```yaml
sdd_record: user
id: USER-plan-request
kind: planning_command
scope:
  stage: document_review
  work: Подготовить план согласованного sample-change
response: Точный ответ пользователя
date: '2026-01-01T00:00:00Z'
inputs: []
status: active
```
````

Замените inputs реальным манифестом исходного комплекта. Разрешение выполнить работу сохраняется в его объеме; согласование версии и waiver требуют совпадения комплекта. Отмену отразите status: cancelled с пояснением/ссылкой на ответ в тексте записи; при замене добавьте новую USER-запись с supersedes, сохранив прежний ответ и историю.
