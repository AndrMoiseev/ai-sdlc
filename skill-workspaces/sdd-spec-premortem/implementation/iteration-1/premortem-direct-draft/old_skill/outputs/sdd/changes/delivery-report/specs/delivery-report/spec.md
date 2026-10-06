---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-report
---
# Отчёт о просроченных доставках

Черновик известной части контракта из [источника](../../../../../docs/report.md). Условные критерии не закрывают вопросы в [state](../../state.md).

## Ежедневная выдача

```yaml
sdd_record: requirement
id: REQ-daily-report
operation: add
```

Диспетчер доставки должен получать отчёт ежедневно в 09:00. Часовой пояс, канал и значение 09:00 для начала формирования либо получения требуют уточнения Q-delivery-contract.

### Отчёт за день

```yaml
sdd_record: acceptance
id: AC-daily-report
requirement: REQ-daily-report
conditions: Согласованы часовой пояс и контракт передачи; наступило время ежедневного отчёта 09:00.
expected: Отчёт за соответствующий день предоставлен диспетчеру по согласованному контракту времени и передачи.
```

## Поля отчёта

```yaml
sdd_record: requirement
id: REQ-report-fields
operation: add
```

Отчёт должен иметь формат CSV и поля delivery_id, overdue_minutes, responsible для просроченных доставок. Правила просрочки, расчёта минут, выбора ответственного и момента среза остаются открытыми в Q-data-contract.

### Представление доставки

```yaml
sdd_record: acceptance
id: AC-report-fields
requirement: REQ-report-fields
conditions: По согласованным правилам в отчёт включена просроченная доставка с известным ответственным.
expected: CSV содержит delivery_id, overdue_minutes, responsible со значениями идентификатора доставки, просрочки в минутах и ответственного по согласованному срезу.
```

### Состав выборки

```yaml
sdd_record: acceptance
id: AC-report-selection
requirement: REQ-report-fields
conditions: Подготовлен контрольный набор с ожидаемой выборкой по согласованному правилу просрочки.
expected: Набор доставок в CSV совпадает с ожидаемой выборкой.
```

## Незавершённая часть контракта

Пустая выборка, неполные данные, недоступный источник, ошибка передачи, повторный запуск и параметры CSV требуют решения Q-failure-contract. Текущие критерии не составляют полной приёмки. Действие получателя и критерий полезности отчёта не определены: Q-report-action.
