# Assignments and context

Read this reference before dispatch, continuation or handoff. The orchestrator
executes the [four-phase workflow](workflow.md); shared
[architect](../../sdd-shared/agents/architect.md) and
[explorer](../../sdd-shared/agents/explorer.md) instructions define the work and
its quality. Use the existing `sdd-spec.architect` and `sdd-spec.explorer` selection
keys directly, without loading the `sdd-spec` skill or its authoring workflow.
Run one assignment at a time. The orchestrator owns dispatch and transitions;
workers request additional research, checks or decisions through it.

## Save the request before dispatch

Use `<report-dir>/assignments/<assignment-id>/request.json` for each bounded
assignment. Give changed scope, inputs, outputs or limits a new assignment ID,
including when continuing the same worker. Keep an earlier request and its result
intact. These are saved workflow records; no additional execution engine is needed.

| Field | Required content |
| --- | --- |
| `report`, `phase`, `role` | Report name; `configuration`, `evidence`, `analysis` or `report`; selected shared role key |
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

## Bind the actual inputs

Record these in `assignment.basis`, using null with a reason for unavailable
observations. Paths alone do not identify an input version.

| Basis member | Evidence to retain |
| --- | --- |
| Source | Established project path, observed `revision`, `dirty`, `source_state`, and the identity artifact when captured |
| Configuration | Exact active configuration path and SHA-256; retained copy or immutable snapshot member with the same content |
| Collection plan | `collection-plan.md`, exact registry revision and retained content identity used by this assignment |
| Primary artifacts | Snapshot, analysis, shortlist/group, diagnoses, cards or previous result actually used, each with a path and content identity |
| Decisions and constraints | Authoritative request or decision references and the exact conditions affecting this assignment |

Before identity capture, use the inspected configuration/source references and
their observed versions; leave uncaptured identity fields null. Retain mutable
inputs needed to reconstruct a request in its `inputs/` directory, including a
configuration or cards version that will later change. Reuse an existing retained
version rather than duplicating it. Keep source bodies at their primary locations;
record paths, declarations and checked versions instead of copying the repository.

At dispatch and return, compare the current basis with the saved request. Source
review must match the snapshot's `source_state` and relevant input provenance.
A known mismatch blocks dependent claims and writing until the orchestrator
reconciles the basis and obtains current evidence. Preserve independently usable
evidence and explain which conclusions are affected. Unknown identity limits a
claim; it is neither a verified match nor a fabricated mismatch. Changed source
scope or configuration requires explicit reconciliation even when an earlier
fingerprint still matches: a fingerprint cannot prove that omitted inputs were read.

Separate expected output changes from changed inputs. A new diagnosis is an output;
changed sources or user decisions can invalidate its basis. Report-file writes may
change Git's `dirty` flag without changing measured sources. For source-free work,
retain the inputs' stated provenance and unknowns; the destination directory does
not supply a source identity for imported reports.

## Register checks in the collection plan

The orchestrator maintains a small run-local command registry in
`collection-plan.md`. Save a nonnegative `registry_revision` and a record for each
check: stable `check_id`, `stage`, exact executable/argument list, working directory,
required environment and tools, input basis, dependency IDs, output/log paths,
timeout and applicable whole-suite deadline. Resolve placeholders before assigning
checks. Retain the version used by each request when the plan changes.

Use `stage: evidence` for identity, existing build/report tasks, `collect` and
`analyze`; use `stage: report` for `rank`. Add another explicit stage only for an
authorized focused check. Resolve each requested ID against the saved revision;
all IDs belong to the assigned stage. Execute them in dependency order, requiring
each prerequisite to succeed before its dependent command starts. An
assignment identifies the exact set; the explorer executes it without substituting
commands or dropping checks. A later configuration/provenance update forms a new
basis for the dependent batch. When a prerequisite fails, skip its dependent
checks and report each unexecuted check with the reason. Continue independent
assigned checks whose prerequisites, basis and limits still hold. If the batch
cannot continue, return its partial result; the orchestrator assigns the remaining
independent checks under a current request without repeating verified successful
commands. A failed measurement family does not close unrelated families.

Research may propose commands and inspect their configuration. Builds, tests,
linters, identity capture and metric commands run only under a checks assignment.
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
| Evidence collection | Fresh explorer, separate from configuration research; dependent batches may continue within this phase after basis revalidation |
| Analysis shortlist | Fresh architect with qualified measurements and scope; save the shortlist before group diagnosis |
| One related candidate group | Fresh architect for each group, including a group selected by the shortlist author; allow bounded owner, consumer, wiring and test investigation |
| Report integration | Fresh architect with the saved shortlist and group diagnoses; continue this author after assigned checks return current evidence |
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

The worker writes `assignments/<assignment-id>/result.json` and returns its path
with a concise disposition. The saved result contains:

| Field | Required content |
| --- | --- |
| `assignment_id`, `report`, `phase`, `role`, `scope` | Identity matching the request; include `kind` for explorer |
| `basis`, `observed_basis` | Assigned inputs and the versions actually inspected; call out mismatches |
| `status`, `completed`, `artifacts` | `completed`, `partial` or `blocked`; finished portion and actual output paths/content identities |
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

1. Read the saved result and verify artifact existence, output ownership and input
   freshness. Keep the worker result separate from the orchestrator's assessment.
   Completion of a command or a write does not establish semantic readiness.
2. Route an incomplete answer or conflicting claim to a bounded follow-up with
   the current basis. Forward primary diagnoses and evidence to the next architect.
   The orchestrator need not read every source body or repeat adequate semantic
   analysis; it checks contracts, missing evidence and phase exit conditions.
3. Confirm through the host that the previous writer has stopped before transferring
   an output. A result's `writing_stopped` statement accompanies host evidence; an
   unknown writer state blocks a successor. Preserve the completed portion and
   record the next writer's exact outputs under the
   [single-writer contract](../../sdd-shared/references/coordination.md#writing-and-handoff).
4. During report validation, freeze the completed cards version used by `rank`.
   Explorer owns `ranked-<n>.json` and optional `ranked-<n>.md`; the integrating
   architect owns `cards.json` and `report.md`. Return the exact ranking result to
   that architect, revalidate any corrected cards, then finish the semantic report.
   A generated ranking table is an input to that report, not its completion.

Maintain a compact orchestrator context: current objective and constraints,
phase/assignment identities, basis, active writer, result links and unresolved
questions. Reopen primary artifacts for detail. A replacement context receives
those saved facts and links, never a dump of conversations, raw measurements or
tool logs. Context replacement preserves unfinished work, limits and uncertainty.
Save these links in [continuation state](continuation.md#save-continuation-state)
and use its resume procedure after interruption or lost context.
