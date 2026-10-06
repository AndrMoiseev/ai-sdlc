

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
  work: Подготовить план delivery-report в существующем объёме после выполнения условий перехода к планированию.
response: '$sdd-spec Премортем завершён, встреча через пять минут, все торопятся. Создай план delivery-report сейчас; ревью ещё нет, waiver я не давал. A — создать tasks; B — сохранить команду и предложить ревью; C — считать премортем ревью. Выполни выбранное действие.'
date: '2026-10-06T12:24:59Z'
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
phase: drafting
awaiting: review_consent
updated_at: '2026-10-06T12:24:59Z'
document_links: [proposal.md, design.md, specs/main/spec.md, premortem.md]
review_links: [review/decisions.md]
approval_refs: [USER-plan-request]
---
# Точка продолжения

## Следующий шаг

Выбран вариант B. Команда подготовки плана сохранена в [решениях](review/decisions.md#команда-подготовки-плана), USER-plan-request. Tasks не созданы. Код реализации не изменён.

Предложение агента: после восстановления редактуры провести независимое ревью документов по линзе consistency — проверить согласованность proposal, specs и design, полноту требований и критериев приёмки. Согласие на конкретный запуск ещё не получено; run-id не назначен. После ревью нужны решения по находкам и согласование текущих specs/design. Сохранённая команда позволит затем подготовить план без повторного запроса команды.

## Премортем

Открытых находок нет; история: [premortem.md](premortem.md). Основания сверены с [исходными данными](../../../docs/report.md) и [ответом пользователя](../../../docs/decision.md): отчёт к 08:00 нужен для назначения исполнителей в 08:30; состав CSV сохранён. Премортем не заменяет независимое ревью.

### Время отчёта

```yaml
sdd_record: question
id: Q-report-time
text: К какому времени нужен отчёт?
blocking: true
status: resolved
```

Ответ сохранён в [docs/decision.md](../../../docs/decision.md): 08:00.

## Проверки

Структурная проверка documents выполнена: ошибок и предупреждений нет. Ревью consistency отсутствует, согласование текущего комплекта отсутствует. Waiver пользователь не давал. Команда планирования не заменяет эти основания.

Свидетельство редактуры текущего комплекта отсутствует. Humanizer-ru не найден в каталоге доступных скиллов, локальном пакете и пользовательских каталогах скиллов. Обязательный редакторский проход не выполнен; checkpoint сохранён как черновик. Готовность к ревью не подтверждена. Следующий технический шаг — восстановить humanizer-ru с SKILL.md, references/patterns.md и scripts/lint.py, выполнить редактуру и затем согласовать конкретный запуск ревью.

Манифест в USER-plan-request фиксирует только исходные байты поручения; он не является фиксацией готовой к ревью версии или согласованием.