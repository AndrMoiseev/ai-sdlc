# Worktree recovery after a base-code fix

Keep the execution blocked while a proven pre-existing defect remains unresolved.
Once its fix is committed on the execution branch and verified, resolve that
specific blocker through `resume` with the fix SHA and check evidence. For an external
HEAD, first obtain explicit acceptance of the clean main tree using the exact-head
resolution in [resume](../flows/resume.md#source-reconciliation). Keep budget,
normative, mode and other unresolved blockers in force.

Inspect `resume.stale_worktrees`. For each unfinished, unintegrated task whose
registered `worktree.base` differs from the execution branch's current HEAD:

1. Stop task roles and record their results, or reconcile lost contexts through
   `resume`. Finish pending procedures and reconcile outstanding integration
   intents. Preserve task files, prior evidence and lifetime budgets.
2. Submit `worktree_refresh` with `reason` and `evidence` identifying the fixed
   base and its verification. This existing execution authorization covers local
   worktree replacement once the main HEAD is reconciled; refresh does not accept an unknown HEAD.
   First preserve unfinished edits in a local task commit and leave the source
   worktree clean, including ignored data. The script creates a new task branch
   and worktree at current HEAD, transfers committed owned changes with a
   three-way merge, and retains the old worktree and branch for recovery.
3. Use the returned worktree path for all subsequent roles. The script replaces
   the task's source baseline and invalidates its candidate and transfer package.
   Old reviews/checks remain historical and budgets retain their usage. Continue
   an active repair cycle; if the previous mandatory check failed and no cycle is
   active, reserve `repair` before retrying, using an available executor or a fresh
   successor. Otherwise finish implementation with the assigned executor.
4. Record executor completion and freeze a new candidate. Give the task explorer
   the current replacement basis and full registry; obtain fresh independent
   evidence, a separate verifier conclusion and reserved review. Historical `baseline_checks`
   remain the record of the original start, not proof that the new base passes.
   Do not repeat the initial baseline stage after transferring implementation.
   Continue the selected execution flow through integration, checks and acceptance.

The operation preserves accepted tasks and the execution branch/index. It rejects
active roles, dirty source worktrees and committed changes outside task ownership.
Preserve and account for that data before retrying. A retained worktree is not
permission to delete it manually. Refresh also provides an explicit rebaseline
for legacy snapshot-based execution; old evidence remains historical even when
the execution branch's base has not changed.

## Interrupted transfer or conflict

Retry a lost response with the identical event. The durable effect under
`runs/<run-id>/effects/<event-id>.json` records the source, replacement, patch and
cleanup checkpoint. A second event ID is not a retry.

On a merge conflict, preserve both worktrees and the saved patch. Inspect the
effect's `precondition.new` path. Launch/register an executor for this task with
that replacement path and the recorded patch; resolve and stage only task-owned
paths there, preserving the external fix. End the resolver with `role_result`,
then submit `worktree_refresh_resolve` with `intent_id` (the original refresh event),
`role_id` and `resolution` describing the actual conflict decisions. This verifies
the resolved tree while retaining the old tree. It still requires fresh
independent checks and review; a conflict resolution is not task acceptance.

If HEAD, either tree or the normative basis changes unexpectedly during recovery,
preserve the artifacts and reconcile that change before proceeding. A failed
refresh never authorizes deleting the original worktree manually.
