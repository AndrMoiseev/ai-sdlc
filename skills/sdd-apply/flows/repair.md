# Repair and bounded continuation

Load [task events](../references/api-tasks.md) and [checks and evidence](../references/api-checks.md) if not already loaded; use installed event help for payload fields.

Read the recorded failure, its exact candidate, AC, logs, and remaining task budgets before changing code. For a code-review finding, apply the [review policy](../references/review-policy.md) before accepting it for repair. Repair only proven violations; retain all other findings in the technical debt journal and continue the plan. Attribute an accepted defect to a task. Unknown ownership or a proven defect outside the approved scope blocks pending resolution. A contract contradiction uses `spec_conflict` through [resume](resume.md).

For `more_checks`, submit `checks_extend` with the requesting `review_round` ID
and additional commands, sources and AC. Keep existing checks. Run the expanded
set independently on the updated candidate, then reserve a new review round.

Submit `repair` before fixes or a no-change retry after a failing mandatory test/linter. Include reason and reproducible evidence; for self-check failure explicitly include `test_failure: true`. One cycle covers the work until the next complete assigned check set. Reserve before work, retain the active cycle through interruption, and let the script close it on the check result. An unavailable runner leaves the cycle unfinished and blocks; do not retry unchanged infrastructure automatically.

For an integrated or accepted task, `repair` preserves the previous worktree in
history and clears its active assignment. Create a new task worktree from current
execution HEAD, retain the original baseline checks as history, then implement
the repair. Do not rerun initial baseline as an admission gate on the known
failing result. Follow
the same candidate, worktree review, integration and acceptance steps; keep the
task's existing budgets. This also handles a final defect after worktree cleanup.

If a recorded repair only repeats checks, the runtime creates an empty local
candidate commit labelled with the repaired task, then an integration candidate
commit. This preserves task attribution even when other tasks have advanced
HEAD. Fresh tasks still need actual owned changes for acceptance.

There are five test-repair cycles per TASK-ID across self, independent, integration, and final stages. Initial implementation and the first failure consume no repair cycle. A successful fifth cycle can proceed. A failed fifth cycle or need for a sixth blocks the whole run. Returning to the same executor, a replacement role, changed phase or new session does not reset counters.

There are three review rounds per TASK-ID, counting the first and all post-integration/final-defect reviews. `review_start` reserves before substantive review. Continue an interrupted round on the unchanged candidate without a second reservation; a new candidate or new substantive review requires a new round. The third passing round can proceed. A blocking third round or need for a fourth blocks the whole run. Test retries and review rounds are separate budgets.

Before handing work back, confirm the reservation succeeded. Reuse the task's executor while its context is available; otherwise register a fresh successor with partial work, remaining AC, decisions and rejected approaches. End writing with `role_result`, submit `candidate` to commit the repaired result, then obtain current checks and review. Keep previous candidate commits and logs as history. A passing old review cannot accept a changed candidate.

For `review_limit_reached` or `test_repair_limit_reached`, preserve active work and reconcile effects already in flight. Report TASK-ID, limit/usage, remaining errors or findings, changes attempted, raw check evidence and the rest of the plan's state. Request one concrete option: a stated finite extension, return to sdd-spec, or stop with a partial result. Explain that this skill's approved budget contract requires that decision. Only `budget_extend` with the user's recorded source/text and increased finite limit permits additional work; general autonomy and elapsed time do not extend a budget.

## Boundary-test findings

For a finding about tests at changed module boundaries, apply the
[test evolution policy](../references/review-policy.md#tests-at-changed-module-boundaries).
Preserve the behavioral guarantee when repairing a mixed test. Restore or add
checks within the approved group through the registry API, retaining the original
baseline and repair counters. A finding that changes the agreed obligation or
architecture returns to sdd-spec; a justified structural retirement alone does
not start a repair cycle.

