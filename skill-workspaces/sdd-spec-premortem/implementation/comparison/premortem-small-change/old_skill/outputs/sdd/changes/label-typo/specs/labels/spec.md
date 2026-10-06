---
schema_version: 1
document_type: spec
change_id: label-typo
language: ru
capability: labels
---
# Текст интерфейса

## Надпись кнопки отправки

```yaml
sdd_record: requirement
id: REQ-submit-label
operation: modify
source:
  kind: specification
  path: docs/labels.md
  requirement: Текст интерфейса
```

В форме отправки кнопка должна называться «Отправить». Исправление затрагивает только буквы надписи; обработчик, права и доступность остаются прежними. Здесь повторено полное существующее требование для исправления реализации; новый контракт не вводится.

### Правильная надпись

```yaml
sdd_record: acceptance
id: AC-submit-label
requirement: REQ-submit-label
conditions: Пользователь открывает форму отправки.
expected: На кнопке отправки отображается «Отправить».
```

### Границы исправления

```yaml
sdd_record: acceptance
id: AC-label-only
requirement: REQ-submit-label
conditions: Исправление сравнивают с исходной версией.
expected: Меняется только надпись «Отпавить» на «Отправить»; обработчик, права и доступность прежние.
```
