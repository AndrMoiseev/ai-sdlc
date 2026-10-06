

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
awaiting: "clarification"
updated_at: "2026-10-06T12:17:13Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Следующий шаг

Восстановить humanizer-ru и выполнить редактуру либо получить явное исключение для текущей версии. После устранения этого ограничения запросить команду планирования. Tasks отсутствует; разрешение на его создание не найдено. Реализацию не начинать.

## Восстановленные основания

При продолжении прочитаны все документы изменения, исходный отчёт и сохранённое решение пользователя. Прежнего итога проверки в state не было; он выполнен заново и сохранён в [resume-check.json](resume-check.json).

SHA-256 текущих proposal, design и spec совпадают с inputs и inputs_after отчёта 20261001T080000Z-prior/consistency и с inputs USER-documents-approved. Старое ревью актуально по версии; согласование применимо. Отсутствие результата в state не отменяет эти свидетельства. Новое независимое ревью не запускалось. Исторические ответы и отчёт сохранены дословно. Более поздних отмен или замен в доступных материалах нет.

Индекс дополнительных линз отсутствует: требуется только consistency. Пояснение, задачи и команда планирования отсутствуют. Запрос продолжить изменение не записан как согласование или команда планирования.

## Проверка источников и границ

Прочитаны src/labels.json, docs/labels.md и change.diff относительно корня проекта. В исходнике submit содержит «Отпавить»; документация задаёт «Отправить». Diff заменяет только эту строку и соответствует объёму proposal и design. Код и diff не изменены.

Проверка ограничена предоставленными материалами. Обработчик, права и доступность описаны как неизменные; их реализация и исполняемые проверки формы не представлены. Поведение интерфейса в запущенном приложении не проверялось. Расширение объёма изменения не требуется по доступному diff.

## Результат структурной проверки

Штатный scripts/run.py check --stage documents завершился с кодом 0: errors и warnings пусты, consistency completed/current, review complete, approved и ready равны true. Это результат структуры и сопоставления сохранённых записей, а не подтверждение завершённой редактуры или разрешение создавать план. Проверка выполнена при восстановлении до записи этого чернового checkpoint; нормативный комплект после проверки не менялся.

## Редактура: не подтверждена

В прежнем state нет свидетельства редакторского прохода. Humanizer-ru не указан в каталоге навыков и не найден среди файлов рабочей папки, C:/Users/Andrew/.agents/skills, C:/Users/Andrew/.codex/skills и C:/Users/Andrew/.codex/plugins/cache. SKILL.md, references/patterns.md и scripts/lint.py этой зависимости недоступны. Редактор, линтер и слепой проверяющий не запускались. Новая проза state сохранена как черновик; готовность к передаче на ревью не заявляется.

Нормативные документы сохранены без изменений. Хеши ниже фиксируют сверенную версию, но не являются свидетельством редактуры:

- design.md: fcea12db1f318b5ddcc721eb8e6a433e8f7ebbdd62bd3553a09fb034d121ff7a
- proposal.md: 08fca42029f572ffdb9f5b9578d450ab7c5d10a1c08f6324d6bcab12908cf457
- specs/main/spec.md: d59f978d20b49a069d2026426f56c2c7e3b03e67ded212cd11145b781b266276

### Восстановление редактуры

```yaml
sdd_record: question
id: Q-editorial-dependency
text: Восстановить humanizer-ru или явно разрешить исключение из редактуры для текущей версии документов и чернового checkpoint?
blocking: true
status: open
```

Основание ограничения: .agents/skills/sdd-spec/references/editorial-pass.md. После восстановления зависимости проверить текущие байты, выполнить предусмотренный проход и итоговый check. Если нормативные документы изменятся, прежнее ревью и согласование станут stale; их нельзя автоматически перенести на новую версию.
