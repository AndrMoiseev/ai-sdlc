# Continue or focus an architecture audit

Use [orchestration](orchestration.md) for assignments, launch records, results and
writer ownership. Continue work from current source paths, task scope and saved
primary materials; do not reconstruct, compare or require an earlier source version.

## Request bounded evidence

An architect requests additional evidence through the orchestrator with:

| Part | Required content |
| --- | --- |
| Question | One unresolved causal or acceptance question and its affected group/card |
| Evidence | Needed observation, source or artifact; what existing records establish |
| Decision | What positive and negative answers change, and what remains unknown |
| Bounds | Owners/consumers/wiring/tests, named output and feasible stopping condition |

First inspect retained primary evidence. Assign explorer research for source/report
inspection or checks for exact registered commands. Expand scope only when an
identified dependency can answer the question; give an unrelated cause its own
assignment. Suspend only dependent conclusions and continue independent work.
A failed measurement source does not close other chains. Preserve useful partial
results and inherited limits; missing execution is a gap, not a successful check.

## Save continuation state

Maintain `<report-dir>/state.md` before dispatch, after handoff and before context
replacement. Keep this short navigation record:

| Content | Required links or observations |
| --- | --- |
| Work | Report, route, phase, objective, scope and applicable user constraints |
| Basis | Current source paths, configuration/collection-plan paths, collection description and decision sources |
| Assignments | Finished/unfinished IDs, worker identity, output ownership and last host-observed state |
| Evidence | Request, launch, result and primary-output paths; assessment of each handoff |
| Open work | Candidate-group/queue paths and keys, shortlist adjustments, diagnoses/cards, unexecuted checks, gaps and unresolved decisions |
| Plan | Current plan path, matched tasks, completed additions and remaining plan updates; read current user decisions from the plan |
| Next step | Exact phase/assignment and its substantive prerequisite or blocker |

State links primary records instead of duplicating them. Worker completion remains
separate from the orchestrator's assessment. Retain unknown observations as unknown.

## Resume after interruption

1. Read state, the active request, collection plan and linked primary artifacts.
   Check their existence and relevance to the remaining task. A summary cannot
   prove a missing result or executed check.
   Resolve the saved collection's [analysis policy](analysis-policy.md) through the
   script; project overrides edited later do not replace it during continuation.
2. Ask the host for the recorded worker's state. Verify that a previous writer
   has stopped before transferring an output; a saved ID alone does not prove it.
3. Read the current sources needed for the pending question. Use the saved scope,
   paths, conclusions and limitations directly. Missing artifacts remain gaps.
4. Continue a live worker only within its bounded phase; new phases/groups and
   replacement workers receive fresh contexts with primary references. Assign a
   new request when the task scope, outputs or limits change.
5. Reread the current plan; reconcile user edits and partially completed additions
   under [plan maintenance](tech-debt-plan.md#apply-user-changes-and-resume-safely).
   Save the completed portion and next step, then finish report and plan delivery.

No comparison of source revisions, fingerprints or material checksums participates
in resumption. Their absence or difference does not trigger a stop, downgrade,
`needs_check`, recollection or repetition of completed work.

## Reconcile a changed basis

Here, basis means task scope, paths and applicable decisions. Revisit a conclusion
when current substantive evidence contradicts it or the requested question changes.

| Substantive change | Follow-up |
| --- | --- |
| Required behavior, scenario or user decision | Revisit affected mechanism, alternatives, acceptance and dependencies |
| A contradictory current declaration, consumer or wiring fact | Inspect the affected mechanism and correct the claim |
| Measurement population, mapping or instrument definition | Explain comparability; collect an affected measurement only when needed for the question |
| Diagnosis, card or prerequisite | Reintegrate affected claims and rank corrected cards |

Keep useful completed diagnoses and their primary links. A graph calculation may
need a whole affected graph because reachability is global. Define that population
explicitly. Semantic questions justify further work; source identity checks do not.

## Explicit focused routes

A focused route requires an explicit request. Bare invocation and general audit
follow the [full workflow](workflow.md); an existing report alone does not select
a shorter route. Maintain project configuration whenever sources are available.

| Requested route | Work and result |
| --- | --- |
| Existing reports with sources | Qualify populations and mappings; `collect` prepares JSONL evidence. Diagnose requested groups using current declarations, then rank and deliver. |
| Source-free reports | Record input paths and known limitations in `collection-input.json`. `collect` calculates available outputs; analysis returns hypotheses and bounded questions, followed by the report. |
| Proposal comparison | Read the named cards, evidence and current sources. Compare mechanisms and effects; rank justified corrected cards and explain ties or gaps. |
| Diff review | Use the supplied diff or requested Git comparison to locate changes. Inspect current contracts and consumers beyond the diff, then follow [reassessment](reassessment.md). No source-version gate is introduced. |
| Reassessment | Read the earlier card, evidence and acceptance. Inspect the current implementation and relevant measurements; report supported, contradicted and untested effects. |
| Plan-only change | Apply the user's assessment/status/priority changes under [plan maintenance](tech-debt-plan.md#apply-user-changes-and-resume-safely), keeping ready before needs_check. Return the plan link; no audit or collection is needed. |

Qualify populations, tools, extraction limits and source/class mapping through
[collection](collection.md#import-existing-reports). Missing coverage stays unknown.
Source-free evidence cannot establish current ownership or implementation feasibility.
Use the same fresh-context and checks contracts for the chosen scope, explaining
any omitted phase or measurement family. Every audit route retains its materials
and finishes with report and plan delivery, including excluded-status notification.
Plan-only changes update the plan directly. Implementing recommendations requires
a separate task.
