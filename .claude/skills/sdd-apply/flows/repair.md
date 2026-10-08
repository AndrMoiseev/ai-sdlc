# Repair and bounded continuation

Read the recorded failure, its exact candidate, AC, logs, and remaining task budgets before changing code. For a code-review finding, apply the [review policy](../references/review-policy.md) before accepting it for repair. Repair only proven violations; retain all other findings in the technical debt journal and continue the plan. Attribute an accepted defect to a task. Unknown ownership or a proven defect outside the approved scope blocks pending resolution. A contract contradiction uses `spec_conflict` through [resume](resume.md).

For `more_checks`, submit `checks_extend` with the requesting `review_round` ID
and additional commands, sources and AC. Keep existing checks. Run the expanded
set independently on the updated candidate, then reserve a new review round.

Submit `repair` before fixes or a no-change retry after a failing mandatory test/linter. Include reason and reproducible evidence; for self-check failure explicitly include `test_failure: true`. One cycle covers the work until the next complete assigned check set. Reserve before work, retain the active cycle through interruption, and let the script close it on the check result. An unavailable runner leaves the cycle unfinished and blocks; do not retry unchanged infrastructure automatically.

There are five test-repair cycles per TASK-ID across self, independent, integration, and final stages. Initial implementation and the first failure consume no repair cycle. A successful fifth cycle can proceed. A failed fifth cycle or need for a sixth blocks the whole run. Returning to the same executor, a replacement role, changed phase or new session does not reset counters.

There are three review rounds per TASK-ID, counting the first and all post-integration/final-defect reviews. `review_start` reserves before substantive review. Continue an interrupted round on the unchanged candidate without a second reservation; a new candidate or new substantive review requires a new round. The third passing round can proceed. A blocking third round or need for a fourth blocks the whole run. Test retries and review rounds are separate budgets.

Before handing work back, confirm the reservation succeeded. Reuse the task's executor while its context is available; otherwise register a fresh successor with partial work, remaining AC, decisions and rejected approaches. End writing with `role_result`, freeze a new candidate, then obtain current independent checks and review. A passing old review cannot accept changed bytes.

For `review_limit_reached` or `test_repair_limit_reached`, preserve active work and reconcile effects already in flight. Report TASK-ID, limit/usage, remaining errors or findings, changes attempted, raw check evidence and the rest of the plan's state. Request one concrete option: a stated finite extension, return to sdd-spec, or stop with a partial result. Explain that this skill's approved budget contract requires that decision. Only `budget_extend` with the user's recorded source/text and increased finite limit permits additional work; general autonomy and elapsed time do not extend a budget.
