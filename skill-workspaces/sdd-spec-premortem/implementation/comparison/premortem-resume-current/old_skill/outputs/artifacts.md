

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
updated_at: "2026-10-06T12:14:47Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md"]
review_links: []
approval_refs: []
---
# Точка продолжения

## Следующий шаг

Восстановить доступ к humanizer-ru и выполнить редактуру текущих документов и checkpoint по references/editorial-pass.md локального sdd-spec. Затем повторить documents-проверку и определить готовность к предложению независимого ревью. Альтернатива — явное исключение пользователя для редактуры этой версии. Исключение пока не получено.

## Проверка предпосылок

Прочитаны proposal.md, design.md, specs/main/spec.md, [premortem.md](premortem.md), [исходные данные](../../../docs/report.md) и [ответ пользователя](../../../docs/decision.md). Они согласованы по получателю, сроку 08:00, трём колонкам CSV и ручному назначению исполнителей в 08:30. Повторный выбор срока и формата не требуется. Нормативные документы при продолжении не изменены.

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт?"
blocking: true
status: "resolved"
```

Ответ сохранён в [docs/decision.md](../../../docs/decision.md): 08:00.

## Проверки и разрешения

Пакет sdd-spec содержит flows, references, templates, scripts, pyproject.toml, uv.lock и agents/openai.yaml. Доступны uv 0.12.5 и Python 3.14.7; запуск scripts/run.py version успешен.

Диагностическая проверка scripts/run.py check --stage documents при продолжении завершилась с кодом 0: errors и warnings пусты. Это проверка структуры, а не завершение редактуры или разрешение перехода. Требуется линза consistency; её отчёт отсутствует. review_status.complete, approval_status.approved и approval_status.ready равны false.

Tasks, отчёты ревью, USER-записи, пояснение и индекс линз в доступных материалах отсутствуют. Согласие на запуск ревью, команда планирования и согласование документов не подтверждены. Ответ в docs/decision.md подтверждает требования, но не эти переходы. Реализация не начата.

## Ограничение редактуры

Свидетельство редактуры сохранённой версии отсутствует. humanizer-ru не найден в каталоге скиллов среды, локальном пакете проекта, C:/Users/Andrew/.agents/skills, C:/Users/Andrew/.codex/skills и установленном кэше плагинов C:/Users/Andrew/.codex/plugins/cache. Его SKILL.md, references/patterns.md и scripts/lint.py недоступны. Редактор, линтер и слепой проверяющий не запускались; успешный проход не заявляется.

Этот checkpoint сохранён как черновик по правилу недоступной зависимости из references/editorial-pass.md. Готовность документов к передаче и независимому ревью не подтверждена. После восстановления зависимости обработать proposal.md, design.md, specs/main/spec.md, premortem.md и новую прозу state.md; исторический ответ пользователя сохранить дословно. Snapshot для согласования не фиксировался. Пояснение пока не предлагалось: по draft этот шаг следует после редактуры.
