

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
Ранее выявлено: отчёт в 09:00 опаздывал к назначению в 08:30. Пользователь выбрал 08:00; вопрос Q-report-time разрешён. Основание ответа: [решение пользователя](../../../docs/decision.md). По [уточнению основания](../../../docs/evidence.md), назначение в 08:30 означает начало утренней сессии диспетчера в рабочие дни. Это уточнение прежнего основания; решение о ежедневном CSV к 08:00 не менялось. Повторный выбор формата не требуется.


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
phase: "drafting"
awaiting: "clarification"
updated_at: "2026-10-06T12:24:00Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md", "premortem.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Следующий шаг
Текущий флоу — revise. Запрошенное уточнение основания сохранено в premortem.md. В отдельном продолжении пользователь выберет новое время отчёта; до этого действует решение 08:00, Q-report-time остаётся разрешённым. Нового решения о времени и команды планирования нет; реализацию не начинать.

## Проверка предпосылок
Сохранённый разбор: [premortem.md](premortem.md). Проверены потребитель, назначение и CSV.

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт?"
blocking: true
status: "resolved"
```

Ответ сохранён в docs/decision.md: 08:00.

## Проверки и редактура

Нормативные документы, исходный отчёт ревью и USER-запись не изменены. Структурная проверка documents перед правкой прошла без ошибок и предупреждений; ревью consistency актуально, USER-documents-approved применимо. Уточнение основания не меняет поведение и нормативный манифест.

Уточнение premortem.md и этот checkpoint сохранены как черновик: humanizer-ru не найден в каталоге доступных скиллов и локальных каталогах скиллов. Обязательная редактура не выполнена; свидетельство редактуры прежней версии также отсутствует. Для завершения прохода нужно подключить humanizer-ru либо получить явное исключение пользователя для этой версии. Готовность к новому ревью не заявляется.
