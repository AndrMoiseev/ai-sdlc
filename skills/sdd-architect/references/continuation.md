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
This independent-chain rule applies to explicitly focused work. A missing or failed
mandatory source blocks the full audit: retain intermediate materials and the
previous live status, explain the prerequisite and propose fixing it first.
Missing execution is a gap, not a successful check.

## Save continuation state

The orchestrator owns `<report-dir>/state.json`. Save it before dispatch, after
recording the actual launch, after assessing a handoff and before context replacement.
Access the saved file exclusively through `audit_state.py read`, `write` and `check`
under the [runtime contract](runtime.md#continuation-state-commands). For an update,
read through the helper, prepare the changed JSON and pass it to `write`.
Direct file reads, editor patches and shell overwrites bypass this contract.
The [schema](../assets/audit-state.schema.json) defines its fields; start with the
[initial example](../assets/audit-state.example.json), replacing its identity,
objective and constraints with the actual request. Keep one continuation file.

| Field | Content and authority |
| --- | --- |
| `schema_version`, `report`, `route`, `phase` | Version 1, report identity matching requests, `full` or `focused`, and the current phase. Use `complete` only after delivery artifacts and the final handoff are verified. |
| `objective`, `constraints` | The sought result and exact conditions; each constraint has `text` and its authoritative `source`. |
| `basis` | Current `source_paths`, `configuration`, `collection_plan`, primary `artifacts` and decision sources in `decisions`. Null means a path has not yet been established. |
| `assignments`, `active_assignment` | Recorded assignment IDs and the one pending assignment, or null. Read scope, outputs, limits and result facts from each assignment's primary files. |
| `assignments[].assessment` | Orchestrator's `status`: `pending`, `accepted` or `follow_up`; retain the `reason`. Link a created follow-up through `next_assignment`. A chain must end in an accepted result before completion. |
| `assignments[].host_observation` | `worker_id`, last observed `state` (`unknown`, `running`, `stopped`), UTC `observed_at` and host evidence `source`. Unknown observations stay null/unknown. |
| `plan` | Current `path`, `matched_tasks`, `added_tasks` and `remaining` operations. The current plan remains authoritative for user decisions. |
| `remaining`, `blockers` | Unfinished groups/checks, missing evidence and open decisions. Preserve relevant object keys and their primary-artifact paths in these short descriptions. |
| `next_step` | One `action`, its recorded `assignment` or null, and its `prerequisite` or null. Complete work has null here. |

Artifact paths are absolute or relative to the audit directory. Source paths name
directories. Primary records are always `assignments/<id>/request.json`,
`launch.json` and `result.json`; the ID supplies their addresses. Use only existing
file paths in `basis.artifacts`, without Markdown anchors or JSONL keys. Keep those
keys in the relevant `remaining` description or the linked diagnosis. Decision and
host sources can identify conversation/tool observations; they are not file-path fields.

Keep full requests, measurements and results in their primary files. An accepted
assessment records a semantic decision by the orchestrator; a worker's `completed`
status alone leaves the assessment pending. For a partial or blocked result, record
the usable portion and remaining question in the reason, then link the new bounded
assignment. Retain prior assessments and their request/result files.

`write` validates the shape and internal references and replaces the file atomically.
It can save unfinished recovery work while primary evidence is missing. Writing
`phase: complete` also requires all material checks to pass. Before dispatch,
phase transition or resumption, run `check`: it also reads primary records, checks
their identities, required paths, assessment evidence and writer observations.
Resolve reported issues before dependent work; preserve blockers and recovery steps
in state meanwhile. A successful check establishes structural consistency only.
The orchestrator still judges meaning, current host state, permissions and plan rows.
It can investigate a reported gap without repeating completed independent work.

## Resume after interruption

1. Use `audit_state.py read` and `check`, then open the active request, collection
   plan and primary artifacts needed for the next action. A missing record is a
   gap to resolve; its saved assessment cannot prove the lost evidence. Keep the
   next recovery action and blockers in state. A summary cannot prove an executed check.
   Resolve the saved collection's [analysis policy](analysis-policy.md) through the
   script; project overrides edited later do not replace it during continuation.
2. Ask the host for the recorded worker's state and save the new observation.
   Verify that a previous writer has stopped before transferring an output; the
   saved observation is historical even when `check` passes. If interruption left
   an active request without a launch/worker ID, inspect host launch evidence before
   redispatch; absence of a launch file does not establish that no worker started.
   Unknown writer state blocks a successor.
3. Read the current sources needed for the pending question. Use the saved scope,
   paths, conclusions and limitations directly. Missing artifacts remain gaps.
4. Continue a live worker only within its bounded phase; new phases/groups and
   replacement workers receive fresh contexts with primary references. Assign a
   new request when the task scope, outputs or limits change.
5. Reread the current plan; reconcile user edits and partially completed additions
   under [plan maintenance](tech-debt-plan.md#apply-user-changes-and-resume-safely).
   Save the completed portion and next step, then finish report and plan delivery.
   For a full audit, publish project status only after all preceding phases succeed.
   Save `phase: complete` after the publication result and final handoff are verified;
   a focused audit completes after its report and plan are verified. Clear the active
   assignment and next step only when their work is finished.
   After a source blocker is resolved, collection uses a new timestamped directory
   as required by runtime; link it from the continued audit and use its aggregate
   input. Never publish stale aggregates from the failed attempt.

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
| Existing reports with sources | Qualify populations and mappings; `collect --focused` prepares JSONL evidence. Diagnose requested groups using current declarations, then rank and deliver. |
| Source-free reports | Record input paths and known limitations in `collection-input.json`. `collect --focused` calculates available outputs; analysis returns hypotheses and bounded questions, followed by the report. |
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
Focused routes never overwrite project status or substitute for a blocked full audit.
