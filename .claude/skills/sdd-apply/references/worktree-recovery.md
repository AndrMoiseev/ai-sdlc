# Worktree recovery after a base-code fix

Keep the execution blocked while a proven pre-existing defect remains unresolved.
Once its fix is committed on the execution branch and verified, resolve that
specific blocker through `resume` with the fix SHA and check evidence. Keep budget,
normative, mode and other unresolved blockers in force.

Inspect `resume.stale_worktrees`. For each unfinished, unintegrated task whose
registered `worktree.base` differs from the execution branch's current HEAD:

1. Stop task roles and record their results, or reconcile lost contexts through
   `resume`. Finish pending procedures and reconcile outstanding integration
   intents. Preserve task files, prior evidence and lifetime budgets.
2. Submit `worktree_refresh` with `reason` and `evidence` identifying the fixed
   base and its verification. This existing execution authorization covers local
   worktree replacement; a stale base alone does not require another user decision.
   The script creates a new detached worktree at current HEAD, saves a binary
   task patch and the old staged diff, transfers owned files with a three-way
   merge, verifies the source and destination, then removes the old worktree.
3. Use the returned worktree path for all subsequent roles. The script replaces
   the task's source baseline and invalidates its candidate and transfer package.
   Old reviews/checks remain historical and budgets retain their usage. Continue
   an active repair cycle; if the previous mandatory check failed and no cycle is
   active, reserve `repair` before retrying, using an available executor or a fresh
   successor. Otherwise finish implementation with the assigned executor.
4. Record executor completion, freeze a new candidate, and obtain fresh independent
   checks and review in the replacement worktree. Historical `baseline_checks`
   remain the record of the original start, not proof that the new base passes.
   Do not repeat the initial baseline stage after transferring implementation.
   Continue the selected execution flow through integration, checks and acceptance.

The operation preserves accepted tasks and the execution branch/index. It rejects
unexpected task commits, active roles and changed/untracked/ignored files outside
task ownership before deleting anything. Preserve and account for such data before
retrying; do not bypass the ownership check with a filesystem deletion.

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
the resolved tree before removing the unchanged old tree. It still requires fresh
independent checks and review; a conflict resolution is not task acceptance.

If HEAD, either tree or the normative basis changes unexpectedly during recovery,
preserve the artifacts and reconcile that change before proceeding. A failed
refresh never authorizes deleting the original worktree manually.
