

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
Планировщик запускает сборку CSV из хранилища доставок заблаговременно, чтобы к 08:00 файл был доступен диспетчеру через существующий канал. Срок готовности определён в [ответе пользователя](../../../docs/decision.md): в 08:30 диспетчер назначает исполнителей по отчёту. Назначение остаётся ручным.

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
Исходный срок 09:00 в docs/report.md был позже назначения исполнителей в 08:30: такой отчёт не мог повлиять на утреннее назначение. В [ответе от 2026-10-01](../../../docs/decision.md) пользователь уточнил срок: отчёт нужен к 08:00. Этот срок внесён в proposal, спецификацию, критерий приёмки и design; Q-report-time в [state](state.md) закрыт. Диспетчер получает список до назначения в 08:30. Колонки CSV и ручное назначение сохранены.


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
updated_at: "2026-10-06T12:07:06Z"
document_links: ["proposal.md", "design.md", "specs/main/spec.md", "premortem.md"]
review_links: []
approval_refs: []
---
# Точка продолжения

## Следующий шаг
Восстановить доступность humanizer-ru и завершить обязательную редактуру изменённых документов, затем выполнить итоговую структурную проверку. Реализацию не начинать. Независимое ревью и планирование не запускались и не согласованы.

## Сохранённое решение
[Ответ пользователя от 2026-10-01](../../../docs/decision.md) закрывает вопрос о времени. Текущий запрос разрешает перенести этот ответ в документы delivery-report. Обновлены proposal.md, specs/main/spec.md (требование и критерий приёмки), design.md и premortem.md. Исходный ответ сохранён дословно в docs/decision.md; docs/report.md остаётся историческим источником с прежним сроком, заменённым этим ответом.

## Проверка предпосылок
Сохранённый разбор: [premortem.md](premortem.md). Проверены потребитель, назначение и CSV. Противоречие между сроком отчёта и временем назначения устранено в документах изменения.

### Время отчёта

```yaml
sdd_record: "question"
id: "Q-report-time"
text: "К какому времени нужен отчёт до назначения в 08:30?"
blocking: true
status: "resolved"
```

Решение: отчёт нужен к 08:00 для назначения исполнителей в 08:30. Основание — [сохранённый ответ пользователя](../../../docs/decision.md). Повторное уточнение времени не требуется. Открытых вопросов нет.

## Проверки и ограничения
Свидетельства редактуры предыдущей версии нет. humanizer-ru не найден в каталоге доступных скиллов, локальном пакете и установленных каталогах скиллов среды; SKILL.md, references/patterns.md и scripts/lint.py этой зависимости недоступны. Редактура не выполнена; изменённые документы сохранены как черновик. Для завершения нужно подключить humanizer-ru либо получить явное исключение пользователя для этой версии по references/editorial-pass.md пакета sdd-spec. Готовность к передаче на ревью не подтверждена; snapshot для согласования не снимался.

Ревью и согласования отсутствуют; устаревших отчётов и согласований не найдено. tasks.md отсутствует, команды планирования нет. Код реализации не изменён.

Предварительная структурная проверка documents: exit 0, errors: [], warnings: []; обязательная линза consistency отсутствует, review complete: false, approval approved: false, ready: false. Это не итоговая проверка после редактуры и не согласование версии.
