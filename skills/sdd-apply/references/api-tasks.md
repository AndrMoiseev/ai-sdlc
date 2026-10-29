# Task transitions

Use the [common event envelope](api.md) and `execute.py --help-event <type>`
for the current operation's fields. The selected execution flow owns ordering;
help owns payload names. Load [checks and evidence](api-checks.md) before check
or candidate work and [review policy](review-policy.md) before acting on findings.

Role registration attests an actual launch; role_result only ends that role's
work. Review_start reserves a round before review; review_result returns the
separate test_integrity assessment. Only current
evidence, passing review and a confirmed task commit permit acceptance.

`candidate` commits the stopped executor's owned changes locally before checks
and review. A candidate commit is an unaccepted result. Execution uses
task worktrees. After transfer, freeze and verify a new integration commit;
`commit` confirms that reviewed commit and `accept` records task acceptance.
Use [candidate identity](api-checks.md#candidate-identity) for the commit transition and its scope.

For an approved refactoring check replacement, use the staged registry contract
in [checks and evidence](api-checks.md#approved-refactoring-revisions).
Acceptance confirms applicability atomically; resume returns the last confirmed
revision and unfinished transition separately. Preserve both during repair or
resume. A pending transition keeps its original authorization and budgets.

Load additional contracts at their transition: [repair](../flows/repair.md) for
failed checks or proven violations, [worktree recovery](worktree-recovery.md) for
a stale/conflicted worktree, [resume](../flows/resume.md) for lost roles, normative
conflicts, plan revision or authorization changes, and [finalize](../flows/finalize.md)
after all tasks are accepted. Preserve lifetime budgets across all transitions.

Task states: pending, running, verifying, reviewing, integrating, repairing,
committing, blocked, accepted. Run states: active, blocked, completed.

Explorer registration adds `assignment` to `role_register`; its ID equals the
role ID. Scope, basis and full check set are validated before execution. Research
accepts task or null scope and finishes with a typed `role_result.result` containing
`kind: research`, nonempty `answer`, and lists `references`, `inspected_scope`,
`limitations`, `assumptions`, `questions`. Preserve the actual host `trace`.
The saved role supplies the assignment identity, scope, basis and launch evidence;
research does not create a second event journal or accept a task.