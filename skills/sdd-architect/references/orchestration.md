# Assignments and context

Read this reference before dispatch, continuation or handoff. The orchestrator
executes the [workflow](workflow.md); shared
[architect](../../sdd-shared/agents/architect.md) and
[explorer](../../sdd-shared/agents/explorer.md) instructions define the work and
its quality. Use the existing `sdd-spec.architect` and `sdd-spec.explorer` selection
keys directly, without loading the `sdd-spec` skill or its authoring workflow.
Run one assignment at a time. The orchestrator owns dispatch and transitions;
workers request additional research, checks or decisions through it.
Project settings remain read-only for the orchestrator and all workers.
Their modification belongs to user-initiated `sdd-setup`, never to audit-time approval.
Before assigning work that depends on thresholds, weights or budgets, obtain the
[analysis policy](analysis-policy.md) through `metrics.py policy`. Pass the
required values or saved file path to the worker. Use the collection as the
policy source after collection.
Workers must not read defaults or merge project overrides to obtain actual values.
The orchestrator alone maintains the [tech debt plan](tech-debt-plan.md). Workers
receive relevant current task cards and user decisions as read-only inputs; keep
their write scopes inside the assigned audit. Reread user-edited plan entries before
the orchestrator applies additions or a requested plan change.

## Save the request before dispatch

Use `<report-dir>/assignments/<assignment-id>/request.json` for each bounded
assignment. Give changed scope, inputs, outputs or limits a new assignment ID,
including when continuing the same worker. Keep an earlier request and its result
intact. These are saved workflow records; no additional execution engine is needed.

| Field | Required content |
| --- | --- |
| `report`, `phase`, `role` | Report name; `configuration`, `evidence`, `analysis`, `ranking`, `report` or `publication`; selected shared role key |
| `objective`, `constraints` | One bounded outcome and the applicable user decisions, required behavior, scope, language and permission limits, with their sources |
| `assignment` | `id`, `scope`, `basis`, `read_scope`, `outputs`, `limits`; add the explorer fields below for explorer work |
| `instructions` | Shared role file and only the current assignment's phase instructions and required reference sections |
| `expected_result` | Assigned artifact paths, completion criterion, required findings and the result fields below |

Use `scope.project` for the established project identity, `scope.work` for this
report identity and `scope.task` for an existing task identity or null. Keep exactly
these three string-or-null fields. An audit does not create a fictitious SDD TASK.
Preserve exact user conditions and source fields when shortening a request.
Resolve every artifact path before launch. Grant writes to named outputs; all
product sources, settings and other workers' artifacts remain read-only.

For explorer, `assignment` follows the
[shared assignment contract](../../sdd-shared/references/explorer.md#assignment):
`kind: research` plus `question`, or `kind: checks` plus `check_ids`, `stage` and
`registry_revision`. Validate this inner object, not the enclosing request.
The architect uses the common fields for its authoring scope; it is not an explorer
research or checks assignment. Limits are explicit time and output bounds chosen
for this assignment, with any inherited deadline or retry budget. Distinguish
these operating constraints from measured consumption or host context capacity.

Include the shared messaging rule: send a result, blocker or needed decision;
save required reports and evidence in full. Supply primary artifact links and a
compact account of established facts, limitations and remaining work. A fresh
worker receives the role and bounded request, not the parent conversation or the
previous worker's transcript. The orchestrator keeps the workflow map; later-phase
instructions enter a worker's context only when that phase is assigned.

## Describe the current inputs

Use a nonempty `assignment.basis` containing the current scope and source,
configuration and material paths. The shared Explorer contract leaves the contents
of this object to the calling skill. For this audit, use:

| Basis member | Content |
| --- | --- |
| `source_paths` | Current checkout and relevant source directories/declarations; empty for source-free work |
| `configuration` | Link to this audit's `collection-input.json`; paths inside its contents are project-relative |
| `collection_plan` | Collection-plan path; exact command-registry revision belongs to checks assignments |
| `artifacts` | Collection description, candidate groups/queue and metric JSONL paths/keys, shortlist, diagnoses, audit cards or existing plan tasks needed for this task |
| `decisions` | Authoritative requests, decisions and exact conditions affecting the task |

Check that inputs exist and answer the assigned question. Source review uses the
current declarations and consumers. No captured source identity, content hash,
checksum, immutable input copy or dispatch/return version comparison is required.
Missing or different version identifiers cannot block writing or reduce readiness.
Retain actual substantive limitations, missing files and contradictory observations.

A new diagnosis is an output; a changed task or substantive contradiction can require
a new bounded assignment. Recording a report in a later commit supplies ordinary
repository history only. For source-free work, retain supplied population and tool
provenance without attaching the destination repository's identity to those inputs.

## Register checks in the collection plan

The orchestrator maintains a small run-local command registry in
`collection-plan.md`. Save a nonnegative `registry_revision` and a record for each
check: stable `check_id`, `stage`, exact executable/argument list, working directory,
required environment and tools, input basis, dependency IDs, output/log paths,
timeout and applicable whole-suite deadline. Resolve placeholders before assigning
checks. Retain the version used by each request when the plan changes.

Use `stage: evidence` for existing build/report tasks and `collect`;
use `stage: ranking` for `rank`, and `stage: publication` for the final `status`
command after report and plan completion. Add another explicit stage only for an
authorized focused check. Resolve each requested ID against the saved revision;
all IDs belong to the assigned stage. Execute them in dependency order, requiring
each prerequisite to succeed before its dependent command starts. An
assignment identifies the exact set; the explorer executes it without substituting
commands or dropping checks. A later configuration/provenance update forms a new
basis for the dependent batch. When a prerequisite fails, skip its dependent
checks and report each unexecuted check with the reason. In a full audit a required
source failure blocks further work and preserves the previous project status;
explain the prerequisite to the user. In focused work, continue independent
assigned checks whose prerequisites, basis and limits still hold. If the batch
cannot continue, return its partial result; the orchestrator assigns the remaining
independent checks under a current request without repeating verified successful
commands. Do not switch a blocked full audit to focused mode without a user request.

Research may propose commands and inspect their configuration. Builds, tests,
linters and metric commands run only under a checks assignment.
The orchestrator registers a proposed follow-up before dispatching it. Preserve
existing permission and time limits across retries or replacement workers.

This registry belongs to this audit, not to specification-document validation.
Execute the registered metric/build commands directly; the shared specification
document checker is not their runner. If a command needs an interpreter or script,
register it explicitly with its arguments. Never treat a report's command text as
permission to execute it. Capture actual command, cwd, outcome and raw evidence;
the checks result links them instead of returning full logs in chat.

## Choose the context boundary

| Assignment | Context and permitted continuation |
| --- | --- |
| Configuration research | Fresh explorer; bounded follow-up may continue only this research on its updated request |
| Evidence collection | Fresh explorer, separate from configuration research; dependent batches may continue within this phase with current task paths and scope |
| Analysis shortlist | Fresh architect with computed candidate groups/queue, qualified measurements and scope; explain shortlist adjustments before group diagnosis |
| One related candidate group | Fresh architect for each group, including a group selected by the shortlist author; allow bounded owner, consumer, wiring and test investigation |
| Recommendation integration | Fresh architect in the analysis phase with the shortlist and group diagnoses; author cards |
| Final report | Fresh architect with diagnoses, cards and validated ranking; author report.md |
| Ranking or further checks | Separate explorer checks assignment; the integrating architect requests it through the orchestrator and suspends dependent writing |

A group is the connected problem and its causal question, not an arbitrary file
or module. Its request names the required owner, consumers, wiring and tests and
links [focused diagnosis](diagnosis.md#request-focused-code-diagnosis). A materially
larger or unrelated problem needs a separate bounded request. Keep diagnoses in
`diagnoses/<group-id>/diagnosis-<n>.md`; group workers never append to one shared
`diagnosis.md`. That file is the shortlist and index. After the shortlist author's
verified stop, the orchestrator maintains its result links and unresolved status;
semantic revisions return to an assigned architect.

Within one phase and bounded problem, continue a live worker only after it checks
the current request, inputs and completed portion. Start a fresh context at every
new phase and every new diagnosis group. If the remaining scope no longer fits
or the worker cannot reliably preserve its constraints and evidence, save a partial
result, stop dependent writing and return it. The orchestrator divides the remaining
question and dispatches a fresh worker from primary artifacts. Do not hand off a
summary of a summary as the evidence for a claim.

Use the [shared resolver](../../sdd-shared/references/subagents.md) before each new
launch and preserve its launch parameters, including Codex `fork_turns: none`.
Check that the host can provide the required boundary. Unsupported isolation or
launch capability blocks the dependent assignment; a role name is not proof of
capability. Keep a live worker's selection fixed when continuing it.

## Retain launch and result evidence

The orchestrator writes `assignments/<assignment-id>/launch.json`. Save the resolver
result, capability observations, actual launch arguments, host worker identity and
trace, and runtime-observed model/effort. For continuation, reference the original
launch and record the actual delivery to that worker. Requested selection and
observed execution remain separate; unobserved model, effort, tokens or context
usage are null. Do not infer a numeric context limit from the chosen profile.
Store the host worker identity in `worker_id`, or null while it is unknown;
`state.json` host observations must name that same worker.

The worker writes `assignments/<assignment-id>/result.json` and returns its path
with a concise disposition. The saved result contains:

| Field | Required content |
| --- | --- |
| `assignment_id`, `report`, `phase`, `role`, `scope` | Identity matching the request; include `kind` for explorer |
| `basis`, `observed_basis` | Assigned scope/paths and the actual sources/materials inspected; call out substantive gaps |
| `status`, `completed`, `artifacts` | `completed`, `partial` or `blocked`; finished portion; `artifacts` is an array of primary output file paths, absolute or relative to the audit directory. Keep keyed evidence references in findings. |
| `findings`, `inspected_scope` | Facts and conclusions with primary references; separate observation, interpretation and proposal |
| `limitations`, `remaining` | Gaps, assumptions, contradictions, capability limits and bounded next questions with decision consequences |
| `launch`, `writing_stopped` | Saved launch reference and the worker's statement that writing has stopped |

Research adds the answer and cited sources. Checks adds each assigned check's
actual outcome, exact registry binding, command/log and machine-result references,
exit status and skips/failures. Unavailable counts remain null. An architect adds
the phase's substantive result: shortlist, bounded diagnosis, or integrated cards
and report. Keep full raw reports and tool logs in their assigned files. Compact
messages retain critical conditions, exact source fields, blockers and primary
links rather than silently dropping them to meet a length preference.

## Accept the handoff

1. Read the saved result and verify artifact existence, output ownership and relevance to the assigned question. Keep the worker result separate from the orchestrator's assessment.
   Completion of a command or a write does not establish semantic readiness.
   Save the assessment and reason in `state.json`; leave it pending until verified,
   or record `follow_up` and the next bounded assignment when more work is needed.
2. Route an incomplete answer or conflicting claim to a bounded follow-up with
   the current basis. Forward primary diagnoses and evidence to the next architect.
   The orchestrator need not read every source body or repeat adequate semantic
   analysis; it checks contracts, missing evidence and phase exit conditions.
3. Confirm through the host that the previous writer has stopped before transferring
   an output. A result's `writing_stopped` statement accompanies host evidence; an
   unknown writer state blocks a successor. Preserve the completed portion and
   record the next writer's exact outputs under the
   [single-writer contract](../../sdd-shared/references/coordination.md#writing-and-handoff).
4. During ranking, keep the card author stopped while explorer reads the completed cards.
   Explorer owns `ranked-<n>.json` and optional `ranked-<n>.md`; the integrating
   architect owns `recommendations/<id>.md` and the compact `cards.json` metadata.
   Return failures to that author and rerank corrected
   cards. Give the successful result to the fresh final-report architect, which owns `report.md`.
   A generated ranking table is an input to that report, not its completion.

After accepting the result, clear `active_assignment`, save the next step and run
the continuation-state check before dependent work. Keep the latest host observation
with its time/source separate from the worker's own `writing_stopped` statement.

Maintain a compact orchestrator context: current objective and constraints,
phase/assignment identities, basis, active writer, result links and unresolved
questions. Reopen primary artifacts for detail. A replacement context receives
those saved facts and links, never a dump of conversations, raw measurements or
tool logs. Context replacement preserves unfinished work, limits and uncertainty.
Save these links in [continuation state](continuation.md#save-continuation-state)
and use its resume procedure after interruption or lost context.
