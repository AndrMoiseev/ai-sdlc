---
schema_version: 1
document_type: "spec"
change_id: "label-typo"
language: "ru"
capability: "main"
---
# Наблюдаемое поведение

## REQ-label-text

```yaml
sdd_record: requirement
id: REQ-label-text
operation: add
```

Кнопка показывает «Отправить» вместо «Отпавить»; обработчик и доступность прежние.

### Критерий приемки

```yaml
sdd_record: "acceptance"
id: "AC-label-correct"
requirement: "REQ-label-text"
conditions: "Открыта форма отправки"
expected: "Текст кнопки — Отправить"
```
