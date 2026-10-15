# Оформление заказа · пример исполнения
Run: illustrative-demo · revision 12
active · sequential · accepted 1/11
Snapshot: 2026-10-15T12:00:00Z

Waves group planned parallel work. Task dependencies require acceptance; execution mode and launch checks still apply. Integration is sequential.

- Wave 1: TASK-database-schema; after acceptance: none; Completed; accepted 1/1
- Wave 2: TASK-ui-shell; after acceptance: none; In progress; accepted 0/1
- Wave 3: TASK-orders-api; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1
- Wave 4: TASK-order-form; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1
- Wave 5: TASK-validation; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1
- Wave 6: TASK-notifications-api; after acceptance: TASK-ui-shell; Waiting for dependencies; accepted 0/1
- Wave 7: TASK-notification-panel; after acceptance: TASK-ui-shell; Waiting for dependencies; accepted 0/1
- Wave 8: TASK-checkout-flow; after acceptance: TASK-orders-api, TASK-notifications-api; Waiting for dependencies; accepted 0/1
- Wave 9: TASK-accessibility; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1
- Wave 10: TASK-end-to-end-tests; after acceptance: TASK-checkout-flow; Waiting for dependencies; accepted 0/1
- Wave 11: TASK-validation-migration; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1

- TASK-database-schema: accepted; review 1/3; test repairs 0/5; commits none
- TASK-ui-shell: running; review 0/3; test repairs 0/5; commits none
- TASK-orders-api: pending; review 0/3; test repairs 0/5; commits none
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-order-form: pending; review 0/3; test repairs 0/5; commits none
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-validation: pending; review 0/3; test repairs 0/5; commits none
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-notifications-api: pending; review 0/3; test repairs 0/5; commits none
  - Waiting for acceptance: TASK-ui-shell
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-notification-panel: pending; review 0/3; test repairs 0/5; commits none
  - Waiting for acceptance: TASK-ui-shell
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-checkout-flow: pending; review 0/3; test repairs 0/5; commits none
  - Waiting for acceptance: TASK-orders-api, TASK-notifications-api
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-accessibility: pending; review 0/3; test repairs 0/5; commits none
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-end-to-end-tests: pending; review 0/3; test repairs 0/5; commits none
  - Waiting for acceptance: TASK-checkout-flow
  - Sequential mode; waiting for: TASK-ui-shell
- TASK-validation-migration: pending; review 0/3; test repairs 0/5; commits none
  - Sequential mode; waiting for: TASK-ui-shell

Blockers: []

Technical debt: 0 finding(s). [Journal](technical-debt.md).
