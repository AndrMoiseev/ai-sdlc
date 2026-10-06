

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
updated_at: '2026-10-06T12:28:03Z'
document_links: [proposal.md, design.md, specs/main/spec.md, premortem.md, tasks.md]
review_links: [review/decisions.md]
approval_refs: [USER-documents-approved, USER-consistency-waived, USER-plan-request]
---
# Точка продолжения

## Следующий шаг

Черновик [плана](tasks.md) создан по проверенной команде USER-plan-request. Для завершения редактуры восстановить humanizer-ru либо получить явное исключение пользователя для текущей версии. Затем выполнить редактуру и проверку структуры, зафиксировать версию и предложить независимое ревью плана. Реализацию не начинать.

## Сохранённые решения

Согласование USER-documents-approved, waiver USER-consistency-waived и команда USER-plan-request из [решений](review/decisions.md) применимы: хеши всех трёх нормативных документов совпали с snapshot documents. Отмен и замен нет. Повторное согласование документов и повторная команда планирования не нужны. Waiver относится только к consistency стадии document_review; разрешения на пропуск ревью плана нет.

## Премортем

Открытых находок нет; история: [premortem.md](premortem.md). Сохранённый разбор сверен с [исходными данными](../../../docs/report.md) и [ответом пользователя](../../../docs/decision.md). Время 08:00, назначение в 08:30 и CSV подтверждены. Повторное интервью не требуется.

### Время отчёта

```yaml
sdd_record: question
id: Q-report-time
text: К какому времени нужен отчёт?
blocking: true
status: resolved
```

Ответ сохранён в [docs/decision.md](../../../docs/decision.md): 08:00.

## Выполненная работа и ограничения

Подготовлена одна задача TASK-deliver-daily-report со статусом pending, которая покрывает единственный AC-report-delivered. Подготовка окружения и интеграционная проверка входят в эту задачу. Исходников реализации в рабочей папке нет; конкретные модули, тестовый раннер и команда запуска не выдуманы, их поиск включён в задачу.

## Проверки

Проверка documents выполнена: errors и warnings пусты, consistency waived, approved и ready равны true. Эти результаты подтверждают структуру и применимость записей, а не завершение редактуры. Нормативные документы и исторические ответы пользователя не изменены.

Независимое ревью плана не запускалось; согласия на него и plan_approval нет. После устранения ограничения редактуры потребуется отдельное согласие на запуск ревью по flows/plan.md.

## Редактура

Свидетельства прежней редактуры в state нет; она не подтверждена. humanizer-ru не найден в локальном пакете, пользовательских каталогах skills и доступном кэше plugins. Не найдены SKILL.md, references/patterns.md и scripts/lint.py этой зависимости. Редактура новых tasks.md и авторской прозы state.md не выполнена. Скилл references/editorial-pass.md разрешает сохранить черновик при недоступной зависимости, но запрещает заявлять готовность к передаче и ревью. Самопроверка не заменяет требуемый проход. Согласование и waiver нормативного комплекта сохранены; исключения из редактуры не получено.

Проверка черновика plan выполнена через scripts/run.py: exit 0, errors и warnings пусты; одна задача, выполнено 0 из 1. Ревью plan missing, approved и ready равны false. Это предварительная структурная проверка; итоговый snapshot для ревью не снимался из-за незавершённой редактуры.


# sdd/changes/delivery-report/tasks.md

---
schema_version: 1
document_type: tasks
change_id: delivery-report
language: ru
---
# План реализации delivery-report

Черновик по [proposal](proposal.md), [спецификации](specs/main/spec.md) и [design](design.md). Основание: USER-plan-request в [решениях](review/decisions.md). Редактура humanizer-ru не выполнена: зависимость не найдена. План пока не готов к независимому ревью и не согласован.

### Подготовить и доставить ежедневный CSV

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
    test_description: На контролируемой дате с просроченными доставками выполнить полный путь от ежедневного запуска до доступности CSV диспетчеру; проверить доступность не позднее 08:00, колонки delivery_id, overdue_minutes, responsible и соответствие строк исходным доставкам.
    location: tests/integration/delivery_report (предполагаемое место; уточнить в репозитории реализации)
    run:
      setup_required: В рамках этой задачи найти проектный тестовый раннер, настроить тестовое хранилище, управляемые часы и тестовый существующий канал доставки; записать фактическую команду запуска и выполнить интеграционную проверку ежедневного отчёта.
```

1. В репозитории реализации найти хранилище доставок, планировщик и существующий канал получения файла диспетчером. Установить действующие правила определения просрочки, расчёта overdue_minutes, поля responsible и часового пояса расписания. В доступных материалах нет исходников и команд запуска; пути модулей и тестовый раннер предстоит определить внутри задачи. Если существующих правил нет или они противоречат документам, остановить зависимую часть и уточнить решение, не подменяя его предположением.
2. Собрать CSV с просроченными доставками и согласованными колонками. Подключить ежедневный запуск и передачу через существующий канал так, чтобы файл был доступен диспетчеру к 08:00; это срок получения, а не только время старта сборки. Назначение исполнителей остаётся ручным.
3. В этой же задаче подготовить фикстуры с просроченными и непросроченными доставками и известными значениями полей. Проверить состав строк, значения и заголовок CSV. Выполнить интеграционную проверку из verification с контролируемым временем, включая границу 08:00 и повтор ежедневного запуска на следующую дату.
4. Сохранить фактическую команду, результаты проверок и подтверждение доступности файла через канал диспетчера. Завершать задачу только после выполнения AC-report-delivered.

## Порядок и параллельная работа

Единственный критерий покрыт одной сквозной задачей вместе с тестами. Отдельной задачи на тестирование нет. Межзадачных зависимостей и конфликтов параллельной записи нет; сборку, расписание и доставку проверяют совместно в рамках этой задачи.

## Граница плана

План не добавляет автоматическое назначение исполнителей. Правила пустого отчёта, повторных попыток и новых каналов доставки не заданы согласованными документами и здесь не устанавливаются. Реализация и выполнение тестов в этой сессии не проводятся.
