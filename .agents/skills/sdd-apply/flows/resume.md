# Resume, revision, and handoff

1. Read state through the API and inspect actual host role liveness. Preserve logs, partial changes and external-operation intents. Call `resume` with `host_trace` and `live_contexts`; include `resolutions` only for concretely resolved blockers, each with `reason`, applicable `task_id`, and `evidence`. The script reconciles basis, branch, candidate and lost roles. A recorded active role is not proof that its process survived.
2. Inspect drift, worktrees, index, HEAD and pending effect results through supported operations. After a pre-existing defect is fixed on the execution branch, use [worktree recovery](../references/worktree-recovery.md) for unfinished tasks still based on the old revision. Reuse an identical event after a lost response; let its journal establish whether the effect happened. Do not replay transfer or commit under a new ID merely because the response was missing.
3. For a lost executor, preserve files and hand the successor completed work, remaining AC, findings, decisions and rejected approaches. Register a fresh successor and resolve the lost-role blocker through supported API operations. Resume the saved task phase and active budget reservation; retain prior evidence only where still applicable.
4. On normative drift, stop work against the old basis. For a substantive conflict, submit `spec_conflict` with `reproduction`, `criteria`, and `contract`, plus affected tasks. Return its material and the completed task IDs to sdd-spec without modifying proposal/specs/design/tasks. Apply the revision contract below. After a revised approved plan and execution instruction, submit `revised_plan` with `instruction: {text, source}`.
5. Recheck the saved mode request against current authorization. To change a loaded mode, submit `mode` with `mode`, `source`, `text`, and `isolation_available` where applicable. Start a genuinely fresh orchestrator, then submit `handoff` from the old owner with `new_owner`, `fresh: true`, and actual `launch_ref`. Transfer only state, common contracts, and the new flow. The old owner stops issuing events. If fresh context is unavailable, preserve the blocker rather than claiming to forget loaded instructions.
6. A mode change with preserved unintegrated worktrees can return `mode_switch_worktree`. Keep candidates and request resolution; the package does not automatically integrate them after authorization is withdrawn. A revised run that changes the selected flow likewise requires fresh-context handoff before loading it.
7. Regenerate derived views using [progress](../references/progress.md) and show current blockers, budget use, next supported action and dashboard. Load only the verified mode's flow. When a necessary reconciliation operation is missing, return a partial result with the exact limitation.

## Revision contract

Completed tasks are those marked `accepted` in execution state. Preserve their
plan records and full execution state, including status, commits, evidence,
reviews and budgets: they record work already completed. A new normative basis
does not reset them to `pending`.

Edit only unfinished task records. Append new tasks at the end of the plan with
new IDs and numbers after the existing tasks. If changed requirements need work
on an already completed result, describe that work in a new follow-up task and
retain the completed task unchanged. `revised_plan` rejects a changed or missing
completed record and rejects new tasks inserted before existing ones.

Unfinished tasks return to `pending` for reassessment against the revised basis;
their prior results, commits and continuing budgets remain linked. Preserve run
history. Historical evidence from completed tasks remains historical; final
acceptance still requires fresh checks against the current basis and final HEAD.
