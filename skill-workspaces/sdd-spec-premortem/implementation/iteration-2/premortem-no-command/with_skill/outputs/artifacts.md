

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
updated_at: "2026-10-06T12:25:53Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md", "premortem.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Следующий шаг

Ожидать явной команды планирования. Команды нет; tasks.md не создан.
Продолжение сессии не разрешает переход к плану. Код реализации не изменялся.
Текущий флоу — resume; состояние восстановлено по документам и источникам.

## Сохранённые решения

[USER-documents-approved](review/decisions.md) согласует текущую версию proposal,
specs и design. Хеши совпадают с сохранённым решением и отчётом ревью.
Текущий запрос пользователя: «Продолжи delivery-report с завершённым премортемом и актуальным ревью. Покажи состояние; команды планировать я не давал.»
Новых согласований и разрешений на планирование не записано.

## Премортем

Открытых находок нет; история: [premortem.md](premortem.md).
Основания сверены с [исходными данными](../../../docs/report.md) и
[ответом пользователя](../../../docs/decision.md): цель, получатель, время и CSV
не изменились. Сохранённый разбор использован без повторного интервью.
Выбранное время 08:00 уже отражено в proposal, design и AC-report-delivered.

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт?"
blocking: true
status: "resolved"
```

Ответ сохранён в [docs/decision.md](../../../docs/decision.md): 08:00,
до назначения исполнителей в 08:30. Открытых блокирующих и отложенных вопросов нет.

## Проверки

Проверка documents через scripts/run.py: ошибок и предупреждений нет.
Единственная обязательная линза — consistency; сохранённый отчёт
20261001T080000Z-prior завершён без находок и актуален.
Недостающих или устаревших ревью нет; нового запуска не было.
Согласование USER-documents-approved применимо. Показатель ready относится
к проверяемым скриптом условиям и не заменяет команду планирования или редактуру.
Нормативные документы и исходный отчёт ревью не изменены.

## Редактура: ограничение

Checkpoint сохранён как черновик. Свидетельство прежней редактуры отсутствует.
В доступном каталоге скиллов, локальном пакете и каталогах
C:/Users/Andrew/.agents/skills и C:/Users/Andrew/.codex/skills humanizer-ru
не найден; SKILL.md, references/patterns.md и scripts/lint.py этой зависимости
недоступны. Редактура новой прозы checkpoint не выполнена; готовность к передаче
и новому ревью не заявляется. Это ограничение не меняет хеши нормативного
комплекта и актуальность сохранённого содержательного ревью.
Для завершения редактуры требуется восстановить humanizer-ru либо получить
явное исключение пользователя для этой версии согласно
[правилам редактуры](../../../../.agents/skills/sdd-spec/references/editorial-pass.md).
Исключение не предоставлено. Ожидание команды планирования сохраняется отдельно.
