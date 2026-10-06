

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
Ранее выявлено: отчёт в 09:00 опаздывал к назначению в 08:30. Пользователь выбрал 08:00; вопрос Q-report-time разрешён. Основание ответа: [решение пользователя](../../../docs/decision.md). По [уточнению основания](../../../docs/evidence.md), назначение в 08:30 означает начало утренней сессии диспетчера в рабочие дни. Это уточняет прежнее основание и не меняет решение о ежедневном CSV к 08:00. Повторный выбор формата не требуется.


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
updated_at: "2026-10-06T12:19:33Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md"]
review_links: ["review/decisions.md", "review/20261001T080000Z-prior/consistency.md"]
approval_refs: ["USER-documents-approved"]
---
# Точка продолжения

## Следующий шаг
Текущий флоу: revise. Уточнение основания в premortem.md сохранено по docs/evidence.md. Пользователь выберет новое время отчёта в отдельном продолжении; до этого действует решение 08:00. Q-report-time остаётся разрешённым прежним ответом. Новое время пока не выбрано; повторный выбор CSV не требуется.

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

Структурная проверка documents: ошибок и предупреждений нет. Манифест нормативных документов совпадает с сохранёнными ревью и USER-documents-approved; они актуальны. Proposal, design, specs, исходный отчёт ревью и ответы пользователя не изменены.

Уточнение premortem.md и новая проза state.md сохранены как черновик: humanizer-ru отсутствует в доступном каталоге скиллов и не найден в проверенных пользовательских каталогах. Обязательная редактура, линт и слепая проверка не выполнены; свидетельство прежней редактуры также отсутствует. Для завершения прохода нужно подключить humanizer-ru либо получить явное исключение пользователя для этой версии. Готовность новой прозы к передаче на ревью не подтверждена.