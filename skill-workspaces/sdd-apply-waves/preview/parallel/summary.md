# Оформление заказа · пример исполнения
Run: illustrative-demo · revision 12
active · parallel · accepted 4/11
Snapshot: 2026-10-15T12:00:00Z

Waves group planned parallel work. Task dependencies require acceptance; execution mode and launch checks still apply. Integration is sequential.

- Wave 1: TASK-database-schema, TASK-ui-shell; after acceptance: none; Completed; accepted 2/2
- Wave 2: TASK-orders-api, TASK-order-form, TASK-validation, TASK-accessibility; after acceptance: TASK-database-schema; In progress; accepted 1/4
- Wave 3: TASK-notifications-api, TASK-notification-panel; after acceptance: TASK-ui-shell; In progress; accepted 1/2
- Wave 4: TASK-checkout-flow; after acceptance: TASK-orders-api, TASK-notifications-api; Ready to launch; accepted 0/1
- Wave 5: TASK-end-to-end-tests; after acceptance: TASK-checkout-flow; Waiting for dependencies; accepted 0/1
- Wave 6: TASK-validation-migration; after acceptance: TASK-database-schema; Waiting to launch; accepted 0/1

- TASK-database-schema: accepted; review 1/3; test repairs 0/5; commits none
- TASK-ui-shell: accepted; review 1/3; test repairs 0/5; commits none
- TASK-orders-api: accepted; review 1/3; test repairs 0/5; commits none
- TASK-order-form: reviewing; review 1/3; test repairs 0/5; commits none
- TASK-validation: running; review 0/3; test repairs 0/5; commits none
- TASK-notifications-api: accepted; review 1/3; test repairs 0/5; commits none
- TASK-notification-panel: running; review 0/3; test repairs 0/5; commits none
- TASK-checkout-flow: pending; review 0/3; test repairs 0/5; commits none
- TASK-accessibility: blocked; review 0/3; test repairs 0/5; commits none
- TASK-end-to-end-tests: pending; review 0/3; test repairs 0/5; commits none
  - Waiting for acceptance: TASK-checkout-flow
- TASK-validation-migration: pending; review 0/3; test repairs 0/5; commits none
  - Cannot run alongside: TASK-validation

Blockers: []

Technical debt: 0 finding(s). [Journal](technical-debt.md).
