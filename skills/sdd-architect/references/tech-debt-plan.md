# Maintain the tech debt plan

Read this contract before selecting audit candidates, completing any audit route,
resuming plan updates, or applying a user's plan-only change. The orchestrator owns
`memory/tech-debt/plan/`; audit workers read relevant tasks but write their assigned
audit artifacts. The user can change the plan at any time.

## Separate historical evidence and current decisions

An audit records what its investigation established. Keep completed audit materials
in `memory/tech-debt/audits/<date-time>/` under the [storage contract](runtime.md#report-storage).
The plan accumulates work across audits without the report's display limit. It is not an
SDD implementation plan or authorization to execute a refactoring.

Use this layout:

```text
memory/tech-debt/
  audits/<date-time>/
    report.md
    recommendations/<id>.md
    ...retained evidence and workflow records...
  plan/
    plan.md
    tasks/<task-name>/task.md
```

Choose a descriptive, stable kebab-case task name using the project's thesaurus.
An audit-local ID such as `R1` is not a cross-audit task identity. Keep existing
task paths when titles, source locations or priorities change.

`plan.md` is the current assessment and priority authority. Its active task table
has these columns, in the user's language:

| Task | Status | M/R/C assessment / priority score | Priority rationale / dependencies | Source audit |
| --- | --- | --- | --- | --- |

Link each task to `tasks/<task-name>/task.md` and its source audit to the historical
report. Row order expresses priority; retain equal-priority groups in the rationale.
Use the card for substantive reasoning and evidence. Its copied audit assessment
is the starting basis; later user assessments in the plan take precedence.
Create `plan.md` with an empty table when there are no eligible tasks. Do not create
placeholder task cards; the empty plan remains the destination for later audits.

## Read the plan before investigation

1. Read `plan.md` and inventory existing task directories, including tasks the user
   has closed, deferred or excluded. Read cards relevant to the candidate scope.
2. Match a candidate by problem mechanism, affected responsibility/boundary and
   intended result. A shared file, title or metric is insufficient. Record matches
   and their reasons in the audit's `diagnosis.md`, linking the existing tasks.
3. Reuse an adequate diagnosis for the same unresolved problem. Omit its repeated
   full investigation and card authoring, and state which work was reused rather
   than newly verified. Keep the area eligible for other mechanisms and retain the
   required collection population; a known task does not exclude a whole file or module.
4. Revisit only claims affected by substantive contradictions, changed requirements,
   a missing discriminating fact or a possible recurrence after verified completion.
   Record new evidence and the affected task in this audit. An ambiguous match is
   a bounded investigation question, not grounds to overwrite or silently discard a task.

Pass matched tasks, user assessments and the remaining question in assignments.
Follow [changed-basis reconciliation](continuation.md#reconcile-a-changed-basis);
source-version checks do not participate in this decision.

## Add new tasks after the report

Use the complete validated card set, including cards beyond the report's display limit.
Apply the same procedure to the first and every subsequent audit:

| Audit card status | Automatic plan action |
| --- | --- |
| `ready` | Add a new task to the ready group |
| `needs_check` | Add a new task to the needs-check group with its next discriminating check |
| `observe` | Retain in the audit and notify the user at completion |
| `rejected` | Retain in the audit and notify the user at completion |

Before each write, reread the current plan and relevant task cards. Reconcile user
changes made during the audit; the audit's earlier copy of the plan is not authoritative.

For a new eligible problem, create `tasks/<task-name>/task.md` by copying the
six-section audit card. Keep its substantive content, uncertainties and questions.
Add provenance links to the source audit and exact source card before section 1.
Rebase relative Markdown links from the new directory, including reference-style
links, images and source paths; keep external URLs unchanged. Metric paths/keys
still identify the originating audit's collection. Retain large evidence files
there and link them rather than copying them into every task.

Resolve destinations inside `plan/`, including symlinks. Create only an unused task
directory. For an unrelated name collision choose another descriptive name. For an
existing problem keep its card, assessment, user notes and priority intact, even if
the new audit assigns another status or effect. Put the disagreement and its evidence
in the audit and notify the user; changing an existing task requires a user-directed
plan edit. A later audit does not silently reopen a closed task.

On the first audit use validated ready ordering, followed by the audit's needs-check
investigation order. Unknown effects remain unknown and do not promote a needs-check
task above a ready task. On later audits
insert only new tasks and preserve the relative order of existing tasks within each
status group. Compare new directions using the configured weighted M/R/C sum from
[decision output](decision-output.md#judge-effects-and-readiness) and current user priority decisions;
do not import audit-local rank numbers as global priorities. Compare effect categories
under the same policy before using points from different audits. If the available grounds
cannot place a new task more precisely, append it within its status group and explain
the uncertainty. Preserve equal-score ties, including different effect profiles,
unless a user decision distinguishes them. Keep unknown effects explicit and leave
unresolved tasks unscored.

Every `ready` row precedes every `needs_check` row, regardless of predicted effect,
cost or within-group priority. Use current plan statuses for existing tasks and audit
statuses only to initialize new tasks. An empty group is valid. User-excluded or closed
tasks stay linked in a separate section outside the active table, so later audits can
recognize them without treating them as active work.

## Apply user changes and resume safely

The user may edit assessments, statuses, rationale and priority at any time, directly
or through a request. Apply a plan-only request without starting collection or an audit.
Update the affected plan entries and reasoning; keep the original audit unchanged.
If the user changes an assessment in a working task card, reflect that explicit edit
in the table rather than restoring the copied audit assessment.
When a status changes, place the row in its new status group. Reordering within a group
changes priority; moving a `needs_check` task into the ready group requires changing its
assessment to `ready`. Record that as the user's assessment without claiming new checks
ran. A user-directed inclusion of an `observe` or `rejected` card is an explicit plan
decision: keep it outside the active table until the user assigns `ready` or
`needs_check`. The automatic admission filter still applies to future audits.

After interruption, reconcile existing cards and rows before copying. Use the source
audit/card provenance and semantic matches to recognize completed additions. If a card
exists but its table row is missing, retain the card and finish the row from current
plan/user decisions; never recopy over it. A repeated completion adds no duplicate tasks.

Before completion check:

- Each eligible new problem has one task and a linked table row; known problems link
  to their existing task. Every `ready` row is before every `needs_check` row.
- Existing task content, current assessments and user priority decisions survived.
- New card links resolve from their new location to the intended audit/source evidence.
- The report records additions, reused tasks, disagreements and all excluded cards.

Save plan-update progress and links in audit `state.json` through the
[continuation contract](continuation.md#save-continuation-state). After a card write,
record any remaining table-row update; reconcile the actual plan before marking
that addition finished. Finish with links to both
`report.md` and `plan/plan.md`, counts of added/known tasks, and material gaps.
Explicitly notify the user about `observe` and `rejected` counts and link their cards
or the report section listing every such card. Say when neither status occurred.
Notification is required even when no task was added or no recommendation is ready.
