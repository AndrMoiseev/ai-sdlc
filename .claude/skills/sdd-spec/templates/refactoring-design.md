---
{
  "schema_version": 1,
  "work_kind": "refactoring",
  "document_type": "design",
  "change_id": "sample-refactoring",
  "language": "ru"
}
---
# Рефакторинг ProductId: design

Исходные int-сигнатуры: src/core.py, src/orders.py, src/inventory.py. Целевая граница: ProductId внутри всех трёх модулей; число только на внешней границе. Core вводит тип; orders и inventory используют его независимо друг от друга после core.
Сохраняемый источник: docs/contracts.md, REQ-product-api.


### AC-product-id

```yaml
{
  "sdd_record": "criterion",
  "id": "AC-product-id",
  "purpose": "result",
  "scope": [
    "core",
    "orders",
    "inventory"
  ],
  "conditions": "Преобразование завершено во всей согласованной области",
  "expected": "Во внутренних операциях core, orders и inventory используется ProductId; внешний API остаётся прежним"
}
```

### AC-api

```yaml
{
  "sdd_record": "criterion",
  "id": "AC-api",
  "purpose": "preservation",
  "scope": [
    "core",
    "orders",
    "inventory"
  ],
  "conditions": "Выполняются внешние запросы до, во время и после преобразования",
  "expected": "Числовой product_id, значения ответов и прежние ошибки API сохраняются",
  "source": {
    "kind": "specification",
    "path": "docs/contracts.md",
    "requirement": "REQ-product-api"
  }
}
```

### DEC-product-id

```yaml
{
  "sdd_record": "decision",
  "id": "DEC-product-id",
  "criteria": [
    "AC-product-id",
    "AC-api"
  ]
}
```

## Основание и переход

Замените пример реальными источниками. docs/contracts.md должен существовать и содержать REQ-product-api. При отсутствии спецификации используйте source.kind: evidence с baseline_missing, references, observed и assumptions по общему формату. До преобразования получите исходное свидетельство; пробел не является доказательством эквивалентности.

В этом примере core сохраняет существующие числовые публичные границы, а потребители могут переходить независимо. Если реальный переход требует временных адаптеров, опишите их и добавьте удаление отдельной задачей с проверкой отсутствия обходов. Уточните локальные переходные критерии, until_task и replaced_by по реальному переходу; этот пример показывает постоянные результаты.

При пересмотре DEC добавьте supersedes на существующий исходный DEC или заголовок и объясните замену. Группы тестов описывайте через test_changes в задачах, сохраняя поведенческие обязательства.
