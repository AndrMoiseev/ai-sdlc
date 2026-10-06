

# sdd/changes/delivery-report/design.md

---
schema_version: 1
document_type: "design"
change_id: "delivery-report"
language: "ru"
---
# Дизайн

## Контекст
[Объем](proposal.md), [требования](specs/main/spec.md).

## Модули и контракты
Планировщик запускает сборку CSV из хранилища доставок к 08:00; диспетчер получает файл через существующий канал. Назначение остаётся ручным.

## Термины
Новых терминов нет.

## Риски
Вопросы и ответы сохранены в [state](state.md).


# sdd/changes/delivery-report/premortem.md

# Проверка предпосылок delivery-report

## Основания
[Исходные данные](../../../docs/report.md).

## CSV
Три согласованные колонки: delivery_id, overdue_minutes, responsible; формат не зависит от времени отчёта.

## Время отчёта
Ранее выявлено: отчёт в 09:00 опаздывал к назначению в 08:30. Пользователь выбрал 08:00; вопрос Q-report-time разрешён. Основание ответа: [решение пользователя](../../../docs/decision.md). Повторный выбор формата не требуется.


# sdd/changes/delivery-report/proposal.md

---
schema_version: 1
document_type: "proposal"
change_id: "delivery-report"
language: "ru"
---
# delivery-report

## Проблема и результат
Снизить просрочки: диспетчер использует отчёт до назначения исполнителей.

## Объем
[Спецификация](specs/main/spec.md). Ежедневно к 08:00 диспетчер получает CSV с просроченными доставками. Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер.

## Исключения
Автоматическое назначение исполнителей не входит в объём.

## Влияние
Новый CSV для диспетчера; существующая система назначения не меняется.


# sdd/changes/delivery-report/review/20261001T080000Z-prior/consistency.md

---
schema_version: 1
document_type: "review"
change_id: "delivery-report"
language: "ru"
run_id: "20261001T080000Z-prior"
stage: "document_review"
lens_id: "consistency"
result: "completed_no_findings"
started_at: "2026-10-01T08:00:00Z"
finished_at: "2026-10-01T08:00:00Z"
inputs: [{"path": "design.md", "sha256": "43157ae48be504a93817442541fb0278643bf94504a277485e3f81b0b15d8624"}, {"path": "proposal.md", "sha256": "6dba5ae30685e7586adfc6fa2c4cf153ac6bcd1fe77547485fbcc26371a21083"}, {"path": "specs/main/spec.md", "sha256": "bf01e424450408f148aaea436cb28e0a75c5f32516ddec4ddca02439940849fe"}]
inputs_after: [{"path": "design.md", "sha256": "43157ae48be504a93817442541fb0278643bf94504a277485e3f81b0b15d8624"}, {"path": "proposal.md", "sha256": "6dba5ae30685e7586adfc6fa2c4cf153ac6bcd1fe77547485fbcc26371a21083"}, {"path": "specs/main/spec.md", "sha256": "bf01e424450408f148aaea436cb28e0a75c5f32516ddec4ddca02439940849fe"}]
freshness: "current"
limitations: []
---
# Consistency

Сохранённое независимое ревью: противоречий в комплекте не найдено.


# sdd/changes/delivery-report/review/decisions.md

---
schema_version: 1
document_type: "decisions"
change_id: "delivery-report"
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
inputs: [{"path": "design.md", "sha256": "43157ae48be504a93817442541fb0278643bf94504a277485e3f81b0b15d8624"}, {"path": "proposal.md", "sha256": "6dba5ae30685e7586adfc6fa2c4cf153ac6bcd1fe77547485fbcc26371a21083"}, {"path": "specs/main/spec.md", "sha256": "bf01e424450408f148aaea436cb28e0a75c5f32516ddec4ddca02439940849fe"}]
status: "active"
```


# sdd/changes/delivery-report/specs/main/spec.md

---
schema_version: 1
document_type: "spec"
change_id: "delivery-report"
language: "ru"
capability: "main"
---
# Наблюдаемое поведение

## REQ-report-export

```yaml
sdd_record: requirement
id: REQ-report-export
operation: add
```

Ежедневно к 08:00 диспетчер получает CSV с просроченными доставками. Колонки: delivery_id, overdue_minutes, responsible. Назначение исполнителей выполняет диспетчер.

### Критерий приемки

```yaml
sdd_record: "acceptance"
id: "AC-report-delivered"
requirement: "REQ-report-export"
conditions: "Наступил срок ежедневного отчёта; имеются просроченные доставки"
expected: "Диспетчеру доступен CSV к 08:00 с колонками delivery_id, overdue_minutes, responsible"
```


# sdd/changes/delivery-report/state.md

---
schema_version: 1
document_type: "state"
change_id: "delivery-report"
language: "ru"
phase: "user_review"
awaiting: "planning_command"
updated_at: "2026-10-06T12:20:33Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md", "premortem.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Состояние и следующий шаг

Продолжение проверено через resume. Премортем завершён, документы согласованы, сохранённое ревью актуально. Ожидается явная команда планирования; tasks.md отсутствует и не создавался. Реализация не начата.

Последнее указание пользователя: «Продолжи delivery-report с завершённым премортемом и актуальным ревью. Покажи состояние; команды планировать я не давал.» Оно не разрешает планирование или новый запуск ревью.

Перед следующим переходом нужно восстановить humanizer-ru и подтвердить редактуру либо получить явное исключение пользователя для текущей версии. Такое исключение не получено. Согласование документов не заменяет команду планирования.

## Сохранённые основания

Потребитель, назначение и CSV проверены в [премортеме](premortem.md). Отчёт нужен к 08:00, до назначения исполнителей в 08:30. Формат CSV согласован; автоматическое назначение исключено. Основания: [исходные данные](../../../docs/report.md) и [ответ пользователя](../../../docs/decision.md). Повторять завершённый разбор и выбор формата не требуется.

[USER-documents-approved](review/decisions.md) относится к текущему комплекту proposal, specs и design. Его манифест совпадает с текущими SHA-256. Сохранённый ответ не изменён. Записей planning_command нет.

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт?"
blocking: true
status: "resolved"
```

Ответ сохранён в docs/decision.md: 08:00. Открытых блокирующих и отложенных вопросов нет.

## Проверки

Проверка documents через scripts/run.py выполнена: errors и warnings пусты. Требуется только consistency; сохранённый отчёт 20261001T080000Z-prior/consistency завершён без находок, его inputs и inputs_after совпадают с текущим комплектом. Устаревших или недостающих ревью нет; незавершённых исправлений нет. Новый запуск ревью не выполнялся.

Проверяющий скрипт сообщил approval_status.approved=true и ready=true; USER-documents-approved применим. Это результат проверки сохранённых записей, а не разрешение планировать и не подтверждение редактуры.

## Редактура — не подтверждена

В исходном checkpoint нет свидетельства редактуры текущего комплекта. humanizer-ru не найден в доступном каталоге скиллов, рабочей папке и установках C:/Users/Andrew/.agents/skills и C:/Users/Andrew/.codex/skills. Требуемые SKILL.md, references/patterns.md и scripts/lint.py недоступны. Редактор, линтер и слепая проверка не запускались; успешный проход не заявляется.

Этот checkpoint сохранён как черновик по references/editorial-pass.md локального пакета sdd-spec. Готовность к передаче и новому ревью не подтверждена. Нормативные документы, премортем, историческое ревью и USER-записи не изменены; отсутствие свидетельства редактуры не обозначено как устаревание их манифестов.

## Продолжение

`$sdd-spec` продолжи delivery-report; прочитай state.md, документы и review/decisions.md, сверь актуальность и сохрани ожидание planning_command. Не создавай tasks без явной команды пользователя.
