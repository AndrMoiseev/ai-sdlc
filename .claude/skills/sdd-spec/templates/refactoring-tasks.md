---
{
  "schema_version": 1,
  "work_kind": "refactoring",
  "document_type": "tasks",
  "change_id": "sample-refactoring",
  "language": "ru"
}
---
# Рефакторинг ProductId: tasks

Проверка структуры выполняется отдельно от смысловой полноты области. Несколько задач вносят вклад в один AC-product-id.

### TASK-core

```yaml
{
  "sdd_record": "task",
  "id": "TASK-core",
  "number": 1,
  "scope": [
    {
      "module": "core",
      "paths": [
        "src/core.py"
      ]
    }
  ],
  "contributes_to": [
    "AC-product-id"
  ],
  "preserves": [
    "AC-api"
  ],
  "depends_on": [],
  "status": "pending",
  "verification": [
    {
      "id": "core-local",
      "criteria": [
        "AC-core",
        "AC-api"
      ],
      "test_description": "Проверить локальный результат и сохранение внешнего контракта",
      "location": "docs/contracts.md",
      "run": {
        "setup_required": "Подготовить локальную характеристическую и типовую проверку до преобразования"
      }
    }
  ]
}
```

### AC-core

```yaml
{
  "sdd_record": "acceptance",
  "id": "AC-core",
  "task": "TASK-core",
  "conditions": "Локальная область преобразована",
  "expected": "ProductId используется в core; локальные проверки проходят",
  "lifetime": "persistent"
}
```

### TASK-orders

```yaml
{
  "sdd_record": "task",
  "id": "TASK-orders",
  "number": 2,
  "scope": [
    {
      "module": "orders",
      "paths": [
        "src/orders.py"
      ]
    }
  ],
  "contributes_to": [
    "AC-product-id"
  ],
  "preserves": [
    "AC-api"
  ],
  "depends_on": [
    "TASK-core"
  ],
  "status": "pending",
  "verification": [
    {
      "id": "orders-local",
      "criteria": [
        "AC-orders",
        "AC-api"
      ],
      "test_description": "Проверить локальный результат и сохранение внешнего контракта",
      "location": "docs/contracts.md",
      "run": {
        "setup_required": "Подготовить локальную характеристическую и типовую проверку до преобразования"
      }
    }
  ]
}
```

### AC-orders

```yaml
{
  "sdd_record": "acceptance",
  "id": "AC-orders",
  "task": "TASK-orders",
  "conditions": "Локальная область преобразована",
  "expected": "ProductId используется в orders; локальные проверки проходят",
  "lifetime": "persistent"
}
```

### TASK-inventory

```yaml
{
  "sdd_record": "task",
  "id": "TASK-inventory",
  "number": 3,
  "scope": [
    {
      "module": "inventory",
      "paths": [
        "src/inventory.py"
      ]
    }
  ],
  "contributes_to": [
    "AC-product-id"
  ],
  "preserves": [
    "AC-api"
  ],
  "depends_on": [
    "TASK-core"
  ],
  "status": "pending",
  "verification": [
    {
      "id": "inventory-local",
      "criteria": [
        "AC-inventory",
        "AC-api"
      ],
      "test_description": "Проверить локальный результат и сохранение внешнего контракта",
      "location": "docs/contracts.md",
      "run": {
        "setup_required": "Подготовить локальную характеристическую и типовую проверку до преобразования"
      }
    }
  ]
}
```

### AC-inventory

```yaml
{
  "sdd_record": "acceptance",
  "id": "AC-inventory",
  "task": "TASK-inventory",
  "conditions": "Локальная область преобразована",
  "expected": "ProductId используется в inventory; локальные проверки проходят",
  "lifetime": "persistent"
}
```

### CHECK-whole

```yaml
{
  "sdd_record": "verification",
  "id": "CHECK-whole",
  "criteria": [
    "AC-product-id",
    "AC-api"
  ],
  "test_description": "Проверить весь core, orders, inventory и внешний API на итоговом состоянии",
  "location": "docs/contracts.md",
  "run": {
    "setup_required": "Подготовить сквозную проверку всех потребителей и неизменности API"
  },
  "setup_task": "TASK-core"
}
```

## Обоснование разбиения

Core предоставляет проверяемый тип и совместимые границы; orders и inventory зависят от этого результата, но не друг от друга. Это позволяет независимо преобразовать потребителей после core вместо одной задачи на весь проект. Проверки входят в каждую задачу; CHECK-whole подтверждает результат только в финале. Для реального временного адаптера добавьте задачу удаления и переходный AC по design до согласования плана.
