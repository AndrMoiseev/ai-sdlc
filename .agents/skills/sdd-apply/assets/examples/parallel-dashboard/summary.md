# order-export (demo)
Run: demo-parallel · revision 24
active · accepted 4/8
Snapshot: 2026-10-22T09:00:00Z

Waves group planned parallel work. Task dependencies require acceptance; launch checks still apply. Integration is sequential.

- Wave 1: TASK-001, TASK-002; after acceptance: none; Completed; accepted 2/2
- Wave 2: TASK-003, TASK-004, TASK-005; after acceptance: TASK-001; In progress; accepted 1/3
- Wave 3: TASK-006, TASK-007; after acceptance: TASK-002; In progress; accepted 1/2
- Wave 4: TASK-008; after acceptance: TASK-003, TASK-006; Ready to launch; accepted 0/1

- TASK-001: accepted; review 1/3; test repairs 0/5; commits 1111111111111111111111111111111111111111
- TASK-002: accepted; review 1/3; test repairs 0/5; commits 2222222222222222222222222222222222222222
- TASK-003: accepted; review 1/3; test repairs 0/5; commits 3333333333333333333333333333333333333333
- TASK-004: reviewing; review 1/3; test repairs 0/5; commits none
- TASK-005: running; review 0/3; test repairs 0/5; commits none
- TASK-006: accepted; review 1/3; test repairs 0/5; commits 6666666666666666666666666666666666666666
- TASK-007: verifying; review 0/3; test repairs 0/5; commits none
- TASK-008: pending; review 0/3; test repairs 0/5; commits none

Blockers: []

Technical debt: 0 finding(s). [Journal](technical-debt.md).
