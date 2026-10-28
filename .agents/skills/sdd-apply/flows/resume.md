# Resume, revision, and handoff

Use installed `--help-event` for the selected recovery operation's exact payload.

1. Read full state through the API (`read` with `view: "full"`) and inspect actual host role liveness. Preserve logs, partial changes and external-operation intents. Call `resume` with `host_trace` and `live_contexts`; include `resolutions` only for concretely resolved blockers, each with `reason`, applicable `task_id`, and `evidence`. Resolve each lost role separately using its `role_id` and reconciled successor; resolving one never clears another role's loss. The script reconciles basis, branch, candidate and lost roles. A recorded active role is not proof that its process survived.
2. Inspect drift, worktrees, index, HEAD and pending effect results through supported operations. After a pre-existing defect is fixed on the execution branch, use [worktree recovery](../references/worktree-recovery.md) for unfinished tasks still based on the old revision. Reuse an identical event after a lost response; let its journal establish whether the effect happened. Do not replay transfer or commit under a new ID merely because the response was missing.
3. For a lost executor, preserve files and hand the successor completed work, remaining AC, findings, decisions and rejected approaches. Register a fresh successor and resolve the lost-role blocker through supported API operations. Resume the saved task phase and active budget reservation; retain prior evidence only where still applicable.
4. Preserve the admitted plan scope when working documents change. For a substantive conflict, submit `spec_conflict` with `reproduction`, `criteria`, and `contract`, plus affected tasks. Return its material and the completed task IDs to sdd-spec without modifying proposal/specs/design/tasks. Apply the revision contract below. After a revised approved plan and execution instruction, submit `revised_plan` with `instruction: {text, source}`.
5. Recheck current authorization and task-worktree isolation. Only parallel execution is supported; preserve unsupported legacy states and reconcile them with their original skill version. Preserve legacy source-snapshot evidence as history and obtain fresh commit-bound candidates and checks; do not relabel old passing checks. To transfer coordination, start a genuinely fresh orchestrator, then submit `handoff` from the old owner with `new_owner`, `fresh: true`, and actual `launch_ref`. Transfer saved state, common contracts, and the execution flow. The old owner stops issuing events. If fresh context is unavailable, report the gap.
6. Regenerate derived views using [progress](../references/progress.md) and show current blockers, budget use, next supported action and dashboard. Read [execute-parallel](execute-parallel.md). When a necessary reconciliation operation is missing, return a partial result with the exact limitation.

## Source reconciliation

Resume and new task worktree creation require a clean main source tree; execution artifacts remain separately managed. Preserve dirty changes and ask for the user's commit or discard decision. A clean unexpected HEAD produces `execution_head_changed`. After showing its changes and receiving actual user acceptance, submit a resolution with that reason, the exact observed `head`, `evidence`, and `instruction: {text, source}`. It advances only `execution_head`; it preserves admitted tasks and document records. It does not move the shared specification checkpoint ref or approve a revised plan. Known apply commits advance the execution source automatically. Worktree refresh requires the main HEAD to have already been reconciled. In-flight task worktree edits remain preserved.

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

When the user explicitly chooses a new approved follow-up instead of reopening an
accepted task stopped at its budget, include `completed_followups` in `revised_plan`.
Each entry names `completed_task` and a distinct newly appended `followup_task`
that depends on it. The execution instruction records that authorization. The
completed task must have confirmed commits and no active review or repair.
The operation removes only that task's obsolete budget stop, preserving its full
record and spent counters. Unfinished-task budget stops and unrelated blockers
remain; this mapping cannot authorize another repair of the completed task.

Ordinary final project registries survive revision with their mandatory definitions
and inventory. Prior attempts remain historical; obtain fresh final evidence at
the revised basis after the new tasks are accepted.

Unfinished tasks return to `pending` for reassessment against the revised basis;
their prior results, commits and continuing budgets remain linked. Preserve run
history. Historical evidence from completed tasks remains historical; final
acceptance still requires fresh checks against the current basis and final HEAD.
