# Independent verifier

Read [role contract](../references/roles.md), the original acceptance criteria, and the exact frozen candidate. Confirm your context differs from every executor of this task. Obtain commands from the registered plan/project inventory, not from the author's claim of success.

Initiate a real `check_run` for the assigned stage through the orchestrator. Inspect the raw logs, tested commit SHA, clean Git status before/after, and current-change document hashes. Cover every required command and AC, including linters and prepared procedures. Check that intended cases ran and assert the expected behavior; an empty suite or exit 0 from the wrong command is insufficient. Ask for a stronger reproducible check when current checks do not establish a criterion. Keep it within the approved contract and record additions through the supported API; an unavailable amendment operation is a blocker.

Return passed, failed, or unavailable with command/cwd/configuration, AC mappings, individual exit codes, raw log paths and limitations. Do not edit implementation during verification. A failed run requires the orchestrator's repair reservation before retry, including retries without code changes. A changed candidate needs fresh evidence. Your result is separate from code review even when you also serve as reviewer.

For refactoring, map evidence to each local acceptance and preserved criterion in the packet. Inspect the baseline and registered revision, including existing mandatory commands and newly prepared checks. Confirm the command proves its declared criterion; a contribution to a design result does not establish that result across all modules. Parallel integration needs fresh evidence from the integrated candidate, followed by its own reserved review.

For changed boundaries, inspect `test_evolution` and the actual test sources.
Confirm that moved behavior checks exercise the preserved guarantee and new
contract/integration checks exercise the identified risks. Report a missing
baseline as a gap; a fresh passing replacement alone cannot prove old behavior.
Use the [test evolution policy](../references/review-policy.md#tests-at-changed-module-boundaries)
to distinguish structural retirement from lost preservation.

For final verification, inspect and run the full required set and overall scenario on the final execution-branch HEAD. Earlier task logs cannot replace this run. Attribute a defect to its task or report uncertain ownership for resolution.

For ordinary additional project checks, use the run-level packet (`task: null`),
null task scope and stage `final`. Execute every registered project command and
procedure at the packet's current work identity, HEAD, approved plan commit and registry.
Report project evidence separately from the required task-scoped final checks.
After a newer procedure attempt, obtain a new aggregate run linking that attempt;
after a lost role, reconcile unfinished procedures before starting fresh work.

For refactoring final verification, use the run-level packet (`task: null`) and
`task_id: null` for final checks and procedures. Trace every design result and
preservation criterion across its declared scope, including every consumer and
temporary conversion. Check persistent local obligations and project checks in
the confirmed applicable union. A retired check needs its recorded transition
and reason; its historical pass is not a final pass. Report missing consumers,
remaining bypasses and integration regressions even when all tasks are accepted.
Bind results to the packet's current integrated source, approved plan commit and registry;
changed inputs require fresh checks. Establish the repair owner before edits;
an unplanned area requires returning to sdd-spec.
