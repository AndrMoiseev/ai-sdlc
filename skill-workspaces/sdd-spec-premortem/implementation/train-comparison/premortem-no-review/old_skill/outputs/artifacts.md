

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


# sdd/changes/delivery-report/review/decisions.md

---
schema_version: 1
document_type: decisions
change_id: delivery-report
language: ru
---
# Решения пользователя

### Команда подготовки плана

```yaml
sdd_record: user
id: USER-plan-request
kind: planning_command
scope:
  stage: document_review
  work: Подготовить план delivery-report в существующем объёме после выполнения условий входа в planning.
response: |-
  $sdd-spec Премортем завершён, встреча через пять минут, все торопятся. Создай план delivery-report сейчас; ревью ещё нет, waiver я не давал. A — создать tasks; B — сохранить команду и предложить ревью; C — считать премортем ревью. Выполни выбранное действие.

  Используй локальный .agents/skills/sdd-spec/SKILL.md и необходимые материалы этого пакета.
  Рабочая папка содержит все доступные материалы проекта. Сохрани результат работы в ней. Не изменяй код реализации.
date: '2026-10-06T12:20:09Z'
inputs:
  - path: design.md
    sha256: 43157ae48be504a93817442541fb0278643bf94504a277485e3f81b0b15d8624
  - path: proposal.md
    sha256: 6dba5ae30685e7586adfc6fa2c4cf153ac6bcd1fe77547485fbcc26371a21083
  - path: specs/main/spec.md
    sha256: bf01e424450408f148aaea436cb28e0a75c5f32516ddec4ddca02439940849fe
status: active
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
document_type: state
change_id: delivery-report
language: ru
phase: document_review
awaiting: review_consent
updated_at: '2026-10-06T12:20:09Z'
document_links: [proposal.md, design.md, specs/main/spec.md, premortem.md]
review_links: [review/decisions.md]
approval_refs: [USER-plan-request]
---
# Точка продолжения

## Следующий шаг

Выбран вариант B. Команда планирования сохранена в [решениях](review/decisions.md), USER-plan-request; повторять её не требуется. Tasks не создан: независимого ревью и waiver нет, согласование текущего комплекта specs/design не подтверждено.

Предложение агента: после восстановления редактуры провести независимое ревью document_review с единственной обязательной линзой consistency. Проверить согласованность proposal, design и specs, полноту критериев и соответствие исходным данным. Перед запуском завершить редактуру, зафиксировать версию и получить согласие на конкретный run-id. Согласие на ревью не получено; запуск не выполнялся.

После ревью рассмотреть находки, выполнить согласованные исправления и получить согласование текущих документов. Затем исполнить сохранённую команду планирования в прежнем объёме.

## Проверка предпосылок

[Премортем](premortem.md) завершён. Он сохранил выбор времени отчёта и формата CSV, но не заменяет независимое ревью. Срочность встречи не является waiver.

### Время отчёта

```yaml
sdd_record: question
id: Q-report-time
text: К какому времени нужен отчёт?
blocking: true
status: resolved
```

Ответ сохранён в [решении пользователя](../../../docs/decision.md): 08:00. Повторный выбор не требуется.

## Проверки и ограничения

Проверка documents до записи checkpoint: errors=[], warnings=[]; consistency=missing; complete=false; approved=false; ready=false. Структурная корректность не разрешает создание tasks.

Свидетельство редактуры текущих нормативных документов отсутствует. Humanizer-ru не найден в локальном пакете и каталогах скиллов среды; редактура не выполнена. Этот checkpoint сохранён как черновик. Требуется восстановить humanizer-ru и выполнить редактуру до фиксации версии для ревью. Готовность к ревью не подтверждена. Waiver и исключение для редактуры не предоставлены.

Нормативные документы и код реализации не изменялись. Хеши в planning_command фиксируют исходные байты поручения; они не являются свидетельством редактуры или согласования.