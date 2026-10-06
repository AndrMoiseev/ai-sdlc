---
schema_version: 1
document_type: spec
change_id: label-typo
language: ru
capability: labels
---
# Текст интерфейса

## Подпись кнопки отправки

```yaml
sdd_record: requirement
id: REQ-submit-label
operation: modify
source:
  kind: specification
  path: docs/labels.md
  requirement: Текст интерфейса
```

В форме отправки кнопка должна называться «Отправить». Исправление затрагивает только буквы подписи: обработчик, права и доступность кнопки остаются прежними.

### Правильная подпись

```yaml
sdd_record: acceptance
id: AC-submit-label
requirement: REQ-submit-label
conditions: Пользователь открывает форму отправки, в которой отображается кнопка отправки.
expected: На кнопке отображается точный текст «Отправить» вместо «Отпавить».
```

### Сохранение поведения

```yaml
sdd_record: acceptance
id: AC-submit-behavior
requirement: REQ-submit-label
conditions: Сравниваются одинаковые состояния формы и права пользователя до и после исправления подписи.
expected: Доступность кнопки и обработчик отправки остаются прежними; исправление не меняет права пользователя.
```