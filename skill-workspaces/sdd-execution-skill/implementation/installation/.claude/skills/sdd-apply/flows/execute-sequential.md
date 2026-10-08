# Sequential execution

Read [API](../references/api.md) and [roles](../references/roles.md). Keep the parallel flow unloaded.

1. Ask the `available` operation for admission. Maintain one unfinished task. If a previous task is running, verifying, reviewing, repairing, committing or blocked, continue it; do not admit another task. A blocked current task blocks the entire run, even when other dependencies would permit work.
2. Register the task's complete checks and inspected project/CI inventory. Launch a fresh executor using [executor](../agents/executor.md) and the host adapter. Register its observed launch, send its generated packet, then submit `start` with explicit owned paths. Before the executor writes, launch/register an independent verifier and run `check_run` at stage `baseline` for existing mandatory checks. Record planned absence only for approved setup requirements.
3. Let the executor implement and self-check. Handle failure through [repair](repair.md). Save `role_result`, confirm writing stopped, and submit `candidate`.
4. Launch a fresh independent [verifier](../agents/verifier.md), register the real context, and run `check_run` with stage `independent`. If checks are unavailable, block. If they fail, reserve repair before editing or retrying.
5. Launch/register a fresh [reviewer](../agents/reviewer.md), or a second role ID in the same independent verifier context. Reserve `review_start` before substantive review. Save its `review_result`; apply [repair](repair.md) for changes or more checks. Count every new substantive review against the same task budget.
6. After passing current evidence and review, call `commit`, inspect its returned SHA, then call `accept`. The script isolates task paths and preserves unrelated index entries. If ownership is ambiguous, block rather than broaden the commit. Regenerate the dashboard if its generation failed after the state event; do not repeat the commit with a new event ID.
7. Only after `accepted`, request the next available task. After all tasks are accepted, use [finalize](finalize.md).

For a resumed execution with multiple previously started tasks, admit no new task until those tasks have been resolved under the current approved mode. Preserve any mode-switch blocker and its evidence.
