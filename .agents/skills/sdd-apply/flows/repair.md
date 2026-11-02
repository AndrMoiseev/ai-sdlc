# Repair and bounded continuation

Load [task events](../references/api-tasks.md) and [checks and evidence](../references/api-checks.md) if not already loaded; use installed event help for payload fields.

Read the recorded failure, its tested commit, AC, logs, and remaining task budgets before changing code. For a code-review finding, apply the [review policy](../references/review-policy.md) before accepting it for repair. Repair only proven violations; retain all other findings in the technical debt journal and continue the plan. Attribute an accepted defect to a task. Unknown ownership or a proven defect outside the approved scope blocks pending resolution. A contract contradiction uses `spec_conflict` through [resume](resume.md).

Collect both lens results before repair or extending checks. For `more_checks`,
submit `checks_extend` with the verification lens's `review_round` ID and additional
commands, sources and AC, or its current
[conclusion basis](../references/api-checks.md#criterion-conclusions).
Keep existing checks. Assign any new assertions to the executor, freeze the updated
candidate and direct Explorer to run the full project test and static-check set.
Only after all required checks pass, launch both review lenses in parallel in new,
separate fresh contexts. Each lens retains its assigned responsibility.

During implementation and repair, the executor runs local tests and fixes failures as often as needed. Self-checks do not consume the orchestrator's budget or require `repair`.

After executor completion and candidate freeze, a failed independent check batch increases the task counter once, regardless of how many checks failed. Submit `repair` with the reason and recorded evidence to reopen the executor before fixes or a no-change retry. This event does not increase the counter. Retain active repair through interruption; the next complete independent check result closes it. An unavailable runner blocks dependent work without consuming a failure attempt; restore its availability before continuing.

For an integrated or accepted task, `repair` preserves the previous worktree in
history and clears its active assignment. Create a new task worktree from current
execution HEAD, retain the original baseline checks as history, then implement
the repair. Do not rerun initial baseline as an admission gate on the known
failing result. Follow
the same candidate, worktree review, integration and acceptance steps; keep the
task's existing budgets. This also handles a defect discovered after worktree cleanup.

If a recorded repair only repeats checks, the runtime creates an empty local
candidate commit labelled with the repaired task, then an integration candidate
commit. This preserves task attribution even when other tasks have advanced
HEAD. Fresh tasks still need actual owned changes for acceptance.

There are five failed independent check batches per TASK-ID. The first failed batch counts as one; the fifth blocks the whole run before another repair. Successful independent checks, executor self-checks, baseline failures, unavailable checks and replay of a recorded result do not increase this counter. Returning to the same executor, a replacement role, changed phase or new session does not reset it. The stored `test_repair_cycles_started` field records this count; `repair` only reopens work.

There are three review rounds per TASK-ID, counting the first and reviews of repairs, including defects discovered after acceptance. Transfer to the execution branch does not require another code review or consume a round. `review_start` reserves before substantive review. Continue an interrupted round on the unchanged candidate without a second reservation; a repaired candidate or new substantive review requires a new round. The third passing round can proceed. A blocking third round or need for a fourth blocks the whole run. Test retries and review rounds are separate budgets.

Before handing work back, confirm `repair` succeeded. Reuse the task's executor while its context is available; otherwise register a fresh successor with partial work, remaining AC, decisions and rejected approaches. End writing with `role_result`, submit `candidate` to commit the repaired result, then obtain current checks and review. Keep previous candidate commits and logs as history. A passing old review cannot accept a changed candidate.

For `review_limit_reached` or `test_repair_limit_reached`, preserve active work and reconcile effects already in flight. Report TASK-ID, limit/usage, remaining errors or findings, changes attempted, raw check evidence and the rest of the plan's state. Request one concrete option: a stated finite extension, return to sdd-spec, or stop with a partial result. Explain that this skill's approved budget contract requires that decision. Only `budget_extend` with the user's recorded source/text and increased finite limit permits additional work; general autonomy and elapsed time do not extend a budget.

## Boundary-test findings

For a finding about tests at changed module boundaries, apply the
[test evolution policy](../references/review-policy.md#tests-at-changed-module-boundaries).
Preserve the behavioral guarantee when repairing a mixed test. Restore or add
checks within the approved group through the registry API, retaining the original
baseline and repair counters. A finding that changes the agreed obligation or
architecture returns to sdd-spec; a justified structural retirement alone does
not start a repair cycle.
