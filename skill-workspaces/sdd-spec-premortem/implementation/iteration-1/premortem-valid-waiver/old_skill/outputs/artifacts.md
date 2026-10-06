

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

### Пропуск consistency

```yaml
sdd_record: "user"
id: "USER-consistency-waived"
kind: "review_waiver"
scope: {"stage": "document_review", "lenses": ["consistency"]}
response: "Разрешаю пропустить consistency для текущего комплекта документов delivery-report."
date: "2026-10-01T08:00:00Z"
inputs: [{"path": "design.md", "sha256": "43157ae48be504a93817442541fb0278643bf94504a277485e3f81b0b15d8624"}, {"path": "proposal.md", "sha256": "6dba5ae30685e7586adfc6fa2c4cf153ac6bcd1fe77547485fbcc26371a21083"}, {"path": "specs/main/spec.md", "sha256": "bf01e424450408f148aaea436cb28e0a75c5f32516ddec4ddca02439940849fe"}]
status: "active"
```

### Команда планирования

```yaml
sdd_record: "user"
id: "USER-plan-request"
kind: "planning_command"
scope: {"stage": "document_review", "work": "Подготовить план delivery-report по согласованным документам"}
response: "Создай план delivery-report по этим документам."
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
document_type: state
change_id: delivery-report
language: ru
phase: planning
awaiting: clarification
updated_at: '2026-10-06T12:22:27Z'
document_links: [proposal.md, design.md, specs/main/spec.md, premortem.md, tasks.md]
review_links: [review/decisions.md]
approval_refs: [USER-documents-approved, USER-consistency-waived, USER-plan-request]
---
# Точка продолжения

## Выполненная работа

Проверены все доступные материалы проекта и решения USER-documents-approved, USER-consistency-waived, USER-plan-request. Сохранённые манифесты применимы к текущим документам; отмен и замен поручения нет. Проверка documents завершилась без ошибок и предупреждений: consistency waived, approved true, ready true. Эти результаты подтверждают структуру и применимость записей, но не редактуру.

Создан черновик [плана](tasks.md): одна задача покрывает AC-report-delivered, включая подготовку окружения и интеграционную проверку. Все задачи pending. Код реализации и согласованные proposal/specs/design не изменены. Команда планирования исполнена в части подготовки черновика; редактура и последующие этапы остаются незавершёнными.

## Следующий шаг

Восстановить humanizer-ru либо получить явное исключение пользователя для текущей версии. Затем завершить редактуру, проверить структуру и зафиксировать снимок версии. После этого предложить отдельный запуск независимого ревью плана. Согласия на этот запуск пока нет; waiver consistency относится только к document_review и не распространяется на plan_review или редактуру. Финальное согласование плана не получено.

## Редактура и ограничения

В каталоге доступных скиллов, локальном пакете и установленных каталогах C:/Users/Andrew/.agents/skills и C:/Users/Andrew/.codex/skills humanizer-ru не найден. Его SKILL.md, references/patterns.md и scripts/lint.py недоступны. Редактор, линтер и слепая проверка не запускались. Свидетельство редактуры исходной версии отсутствует, поэтому она также неподтверждена. Новая проза tasks.md и state.md сохранена как черновик; готовность к передаче на ревью не заявляется.

### Время отчёта

```yaml
sdd_record: question
id: Q-report-time
text: К какому времени нужен отчёт?
blocking: true
status: resolved
```

Ответ сохранён в [решении пользователя](../../../docs/decision.md): 08:00. Проверка предпосылок сохранена в [premortem.md](premortem.md); повторный выбор времени и формата не требуется.

### Зависимость редактуры

```yaml
sdd_record: question
id: Q-editorial-dependency
text: Восстановить humanizer-ru или разрешить исключение из обязательной редактуры текущей версии?
blocking: true
status: open
```

Основание ограничения: .agents/skills/sdd-spec/references/editorial-pass.md. Существующие пользовательские ответы и согласования сохранены дословно в review/decisions.md.
## Проверка черновика плана

Проверка scripts/run.py check --project-root . --change delivery-report --stage plan выполнена: exit 0, errors и warnings пусты. Покрытие AC и граф задач структурно корректны; выполнено 0 из 1 задач. Независимое ревью plan отсутствует, approved false, ready false. Проверка предварительная: она не заменяет обязательную редактуру. Снимок для ревью или согласования не фиксировался.

# sdd/changes/delivery-report/tasks.md

---
schema_version: 1
document_type: tasks
change_id: delivery-report
language: ru
---
# План реализации delivery-report

Черновик по согласованным [требованиям](specs/main/spec.md) и [дизайну](design.md). Основание: USER-plan-request в [решениях](review/decisions.md). Редактура humanizer-ru не выполнена: зависимость не найдена. План пока не готов к независимому ревью и согласованию.

### Подготовить ежедневный CSV и обеспечить его получение к 08:00

```yaml
sdd_record: task
id: TASK-deliver-daily-report
number: 1
covers: [AC-report-delivered]
depends_on: []
cannot_parallel_with: []
status: pending
verification:
  - criteria: [AC-report-delivered]
    test_description: На контролируемом ежедневном запуске с просроченными доставками проверить доступность CSV диспетчеру не позднее 08:00 через существующий канал, колонки delivery_id, overdue_minutes, responsible и соответствие строк исходным доставкам.
    location: tests/integration/test_delivery_report
    run:
      setup_required: В рамках задачи определить стек проекта и команду интеграционных тестов; подготовить тестовое хранилище доставок, управляемые часы и тестовый получатель существующего канала. Зафиксировать команду и выполнить сквозную проверку планировщика, сборки CSV и получения файла.
```

1. Найти в целевом проекте хранилище доставок, правило определения просрочки, планировщик и существующий канал передачи файла диспетчеру. Установить используемый часовой пояс для срока 08:00. Доступные материалы не содержат реализации и команды тестов; эти сведения нужно получить до настройки запуска. Если существующие контракты не определяют нужное поведение, зафиксировать вопрос для уточнения specs/design.
2. Подготовить выборку просроченных доставок и формирование CSV с колонками `delivery_id`, `overdue_minutes`, `responsible`, используя подтверждённые контракты хранилища.
3. Подключить ежедневную сборку и передачу через существующий канал. Настроить начало обработки с учётом времени сборки и передачи, чтобы файл был доступен диспетчеру к 08:00. Назначение исполнителей остаётся ручным.
4. В этой же задаче подготовить фикстуры просроченных и непросроченных доставок, управляемое время и проверку полученного CSV. Проверить состав колонок и строк, значения из тестового хранилища, ежедневный запуск и доступность файла к установленному сроку. Сохранить команду запуска и результаты проверки.

## Порядок и границы

Один AC закреплён за одной задачей. Подготовка окружения и интеграционные тесты входят в неё. Зависимостей между задачами нет; параллельное исполнение не требуется. Путь теста предварительный и уточняется после определения стека проекта.

Выполнение плана ещё не начато. Согласованные документы не задают поведение при пустой выборке и сбоях канала; план не вводит для них новых обязательств. При необходимости изменить контракт следует вернуться к согласованию документов.