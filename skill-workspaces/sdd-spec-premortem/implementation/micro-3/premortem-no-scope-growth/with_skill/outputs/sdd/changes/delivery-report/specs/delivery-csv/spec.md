---
schema_version: 1
document_type: spec
change_id: delivery-report
language: ru
capability: delivery-csv
---
# CSV ежедневного отчёта

Основание — [report.md](../../../../../docs/report.md). Независимая часть черновика: состав колонок согласован для обоих вариантов продукта. Порядок ниже повторяет источник; параметры сериализации ещё не определены.

## Состав колонок

```yaml
sdd_record: requirement
id: REQ-csv-columns
operation: add
```

CSV должен содержать три колонки: `delivery_id`, `overdue_minutes`, `responsible`. Выбор между отчётом и автоматическим назначением не меняет этот состав. Колонка `responsible` сама по себе не задаёт механизм назначения исполнителя.

### Проверка состава

```yaml
sdd_record: acceptance
id: AC-csv-columns
requirement: REQ-csv-columns
conditions: Сформирован CSV ежедневного отчёта.
expected: CSV содержит ровно три колонки с именами delivery_id, overdue_minutes и responsible.
```

### Независимость от варианта продукта

```yaml
sdd_record: acceptance
id: AC-csv-common-contract
requirement: REQ-csv-columns
conditions: Контракт CSV используется в любом из обсуждаемых вариантов продукта.
expected: Состав трёх колонок сохраняется; наличие responsible не требует автоматического назначения.
```

## Граница черновика

Типы и допустимые пустые значения, выборка доставок, расчёт просрочки, экранирование, кодировка, пустой отчёт и ошибки пока не определены источниками. Эти детали не считаются согласованными; их нужно уточнить перед готовностью полного контракта. См. [Q-csv-details](../../state.md#q-csv-details).
