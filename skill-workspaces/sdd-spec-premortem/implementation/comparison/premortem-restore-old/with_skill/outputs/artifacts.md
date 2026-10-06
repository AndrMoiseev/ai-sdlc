

# sdd/changes/label-typo/design.md

---
schema_version: 1
document_type: "design"
change_id: "label-typo"
language: "ru"
---
# Дизайн

## Контекст
[Объем](proposal.md), [требования](specs/main/spec.md).

## Модули и контракты
Изменить только строку в src/labels.json.

## Термины
Новых терминов нет.

## Риски
Вопросы и ответы сохранены в [state](state.md).


# sdd/changes/label-typo/proposal.md

---
schema_version: 1
document_type: "proposal"
change_id: "label-typo"
language: "ru"
---
# label-typo

## Проблема и результат
Исправить опечатку без изменения поведения.

## Объем
[Спецификация](specs/main/spec.md). Кнопка показывает «Отправить» вместо «Отпавить»; обработчик и доступность прежние.

## Исключения
Автоматическое назначение исполнителей не входит в объём.

## Влияние
Только текст кнопки.


# sdd/changes/label-typo/review/20261001T080000Z-prior/consistency.md

---
schema_version: 1
document_type: "review"
change_id: "label-typo"
language: "ru"
run_id: "20261001T080000Z-prior"
stage: "document_review"
lens_id: "consistency"
result: "completed_no_findings"
started_at: "2026-10-01T08:00:00Z"
finished_at: "2026-10-01T08:00:00Z"
inputs: [{"path": "design.md", "sha256": "fcea12db1f318b5ddcc721eb8e6a433e8f7ebbdd62bd3553a09fb034d121ff7a"}, {"path": "proposal.md", "sha256": "08fca42029f572ffdb9f5b9578d450ab7c5d10a1c08f6324d6bcab12908cf457"}, {"path": "specs/main/spec.md", "sha256": "d59f978d20b49a069d2026426f56c2c7e3b03e67ded212cd11145b781b266276"}]
inputs_after: [{"path": "design.md", "sha256": "fcea12db1f318b5ddcc721eb8e6a433e8f7ebbdd62bd3553a09fb034d121ff7a"}, {"path": "proposal.md", "sha256": "08fca42029f572ffdb9f5b9578d450ab7c5d10a1c08f6324d6bcab12908cf457"}, {"path": "specs/main/spec.md", "sha256": "d59f978d20b49a069d2026426f56c2c7e3b03e67ded212cd11145b781b266276"}]
freshness: "current"
limitations: []
---
# Consistency

Сохранённое независимое ревью: противоречий в комплекте не найдено.


# sdd/changes/label-typo/review/decisions.md

---
schema_version: 1
document_type: "decisions"
change_id: "label-typo"
language: "ru"
---
# Сохранённые ответы пользователя

### Согласование документов

```yaml
sdd_record: "user"
id: "USER-documents-approved"
kind: "document_approval"
scope: {"stage": "document_review"}
response: "Согласую proposal, specs и design в приложенной версии."
date: "2026-10-01T08:00:00Z"
inputs: [{"path": "design.md", "sha256": "fcea12db1f318b5ddcc721eb8e6a433e8f7ebbdd62bd3553a09fb034d121ff7a"}, {"path": "proposal.md", "sha256": "08fca42029f572ffdb9f5b9578d450ab7c5d10a1c08f6324d6bcab12908cf457"}, {"path": "specs/main/spec.md", "sha256": "d59f978d20b49a069d2026426f56c2c7e3b03e67ded212cd11145b781b266276"}]
status: "active"
```


# sdd/changes/label-typo/specs/main/spec.md

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


# sdd/changes/label-typo/state.md

---
schema_version: 1
document_type: "state"
change_id: "label-typo"
language: "ru"
phase: "user_review"
awaiting: "planning_command"
updated_at: "2026-10-06T12:21:09Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Следующий шаг

Восстановить обязательную редактуру через humanizer-ru либо получить явное исключение пользователя для текущей версии. После этого нужна явная команда создать план: сохранённое согласование документов само по себе её не заменяет. Tasks отсутствует; реализацию не начинать.

## Восстановление и основания

В прежнем state не было итога премортема. Короткая проверка выполнена заново по [proposal](proposal.md), [spec](specs/main/spec.md), [design](design.md), [исходной строке](../../../src/labels.json), [описанию интерфейса](../../../docs/labels.md) и [diff](../../../change.diff).

Цель — исправить текст кнопки. Исходник содержит «Отпавить», diff заменяет его на «Отправить» и сохраняет ключ submit. Других изменений в предоставленном diff нет. Описание интерфейса подтверждает сохранение обработчика, прав и доступности. Существенных пробелов для этого объёма не обнаружено; вопросов пользователю по фактам не требуется. Исполнение интерфейса не проверялось: предоставлены строковый ресурс, описание и diff.

## Премортем

Премортем: находок нет.

## Сохранённые решения

[USER-documents-approved](review/decisions.md) согласует текущие proposal, specs и design. Все три SHA-256 совпали с сохранённым решением и независимым ревью. Отсутствие прежней записи премортема не отменяет согласование. Новых пользовательских решений нет; команда планирования не найдена.

## Проверки

Проверка через scripts/run.py check --project-root . --change label-typo --stage documents завершилась с кодом 0: errors и warnings пусты, consistency completed/current, approval approved/ready. Это результат структурной проверки и проверки сохранённых записей, а не свидетельство редактуры или разрешение планирования.

Нормативные документы, историческое ревью, ответ пользователя, исходники и diff не изменены. Новый premortem.md не создавался, поскольку находок нет. Блокирующих и отложенных вопросов по содержанию нет.

## Редактура — ограничение

Черновик checkpoint сохранён. Humanizer-ru отсутствует в каталоге доступных скиллов; поиск в локальных каталогах .agents/skills, .codex/skills и .codex/plugins/cache не обнаружил его SKILL.md. Обязательный проход редактора, линтер и слепая проверка не выполнены. Свидетельства прежней редактуры нормативных документов также нет; её завершённость не подтверждена. Готовность к передаче на новое ревью не заявляется.

Для восстановления установить доступный пакет humanizer-ru с SKILL.md, references/patterns.md и scripts/lint.py, затем выполнить references/editorial-pass.md пакета sdd-spec. Альтернатива — явное исключение пользователя для этой версии. Сохранённое согласование документов не трактуется как такое исключение.
