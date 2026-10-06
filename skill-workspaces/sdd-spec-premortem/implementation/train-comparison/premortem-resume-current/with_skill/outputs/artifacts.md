

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
awaiting: "none"
updated_at: "2026-10-06T12:18:57Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md", "premortem.md"]
review_links: []
approval_refs: []
---
# Точка продолжения

## Следующий шаг

Восстановить доступность humanizer-ru и выполнить обязательную редактуру текущих документов и новой прозы checkpoint по references/editorial-pass.md пакета sdd-spec. Затем повторить структурную проверку, учесть выбор пояснения и предложить независимое ревью consistency. До согласия ревью не запускать. План требует отдельной команды и готовности документов; реализацию не начинать.

## Возобновление

Проверены все сохранённые документы изменения и источники docs/report.md и docs/decision.md. Сохранённый ответ пользователя от 2026-10-01 подтверждает время 08:00, состав CSV и ручное назначение исполнителей в 08:30. Эти решения уже отражены в proposal, REQ-report-export, AC-report-delivered и design. Противоречий с источниками не найдено; повторное интервью и пересмотр формата не нужны.

## Премортем

Открытых находок нет; история: [premortem.md](premortem.md).

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт?"
blocking: true
status: "resolved"
```

Ответ: 08:00. Основание: [решение пользователя](../../../docs/decision.md). Вопрос остаётся разрешённым. Открытых блокирующих или отложенных вопросов в сохранённых материалах нет.

## Разрешения и выполненная работа

Выполнена сверка checkpoint, премортема и нормативных документов. Новых требований не добавлено. Нормативные документы и исходные ответы пользователя не изменены.

Отчётов ревью, USER-записей, согласования документов, исключений из ревью и команды планирования нет. Файл tasks.md отсутствует. Текущая просьба продолжить разрешает восстановление и подготовку документов, но не заменяет отдельные условия ревью и планирования.

Пояснение и диаграммы отсутствуют; прежний выбор пояснения не сохранён. Предложение пояснения остаётся следующим действием после редактуры.

## Проверки

Предварительная проверка documents выполнена через scripts/run.py: errors и warnings пусты, exit 0. Обязательная линза consistency — missing; review_status.complete=false, approval_status.approved=false, approval_status.ready=false. Индекс дополнительных линз отсутствует. Это результат структурной проверки, а не подтверждение готовности к ревью или согласования.

Окружение проверки доступно: uv 0.12.5, Python 3.14.7. Полный локальный пакет sdd-spec присутствует. Инструкций AGENTS.md в рабочей папке не найдено.

## Редактура: ограничение

Свидетельства редактуры текущего комплекта нет. Humanizer-ru не найден в каталоге доступных скиллов, локальном пакете и проверенных установках .agents/skills, .codex/skills и .codex/plugins. Его SKILL.md, references/patterns.md и scripts/lint.py недоступны. Редактор, линтер и слепой проверяющий не запускались; редактура не подтверждена.

Этот checkpoint сохранён как черновик по правилу references/editorial-pass.md для недоступной зависимости. Готовность документов к передаче и независимому ревью не заявляется. Следует подключить humanizer-ru либо получить явное исключение пользователя для этой версии; исключение не предоставлено. Снимок для согласия или согласования не создавался.
