# Continue or focus an architecture audit

Read this reference for an evidence request, interrupted audit, changed basis or
explicit focused route. Use [orchestration](orchestration.md) for assignment,
launch, result and context contracts; this reference defines which work to resume.

## Request bounded evidence

An architect requests further evidence through the orchestrator. Retain the request
with the affected diagnosis or integration result, stating:

| Part | Required content |
| --- | --- |
| Question | One unresolved causal or acceptance question, with the affected group or card |
| Evidence | The needed observation, source or artifact and what existing evidence already establishes |
| Decision | What a positive answer changes, what a negative answer changes, and what remains unknown without an answer |
| Bounds | Owners, consumers, wiring or tests to inspect, required output and feasible stopping condition |

The orchestrator first checks whether retained primary evidence answers the
question. Otherwise assign explorer `research` for source/artifact inspection or
`checks` for execution of exact registered commands. Register a proposed command
before dispatch. Put the question and decision branches in the request's existing
instructions and expected result; keep the shared assignment shape unchanged.
Expand read scope only when an identified dependency can answer that question,
and record the reason and new basis. An unrelated cause gets its own assignment.

Suspend only conclusions and writing that depend on the answer. On return, verify
the result and basis, then give its primary references to the responsible architect
under the context policy in [orchestration](orchestration.md#choose-the-context-boundary).
Distinguish a checked negative answer from absent evidence. Missing inputs,
unavailable capability, exhausted limits and incomplete execution are gaps, not
successful checks. Save useful partial results, unresolved decision branches and
the attainable next step; preserve inherited limits across retries. Continue
unaffected work instead of restarting the whole audit. A failed measurement chain
blocks its dependent checks; collect independent families under a current checks
assignment without repeating verified successful commands.

## Save continuation state

The orchestrator maintains `<report-dir>/state.md` before dispatch, after accepting
a handoff, and before interruption or context replacement. Update it when the
basis or next step changes. Use a short navigation record with these contents:

| Content | Required links or observations |
| --- | --- |
| Work | Report identity, selected route, current phase, objective, scope and applicable user constraints |
| Basis | Original and active revision/source state, configuration and collection-plan versions; link their retained identities and decision sources |
| Assignments | Completed and unfinished IDs; current worker identity, output ownership and last host-observed state |
| Evidence | Actual request, launch and result paths, primary outputs and the orchestrator's assessment of each handoff |
| Open work | Affected groups/cards, open or unexecuted checks, gaps, unresolved decisions and remaining limits |
| Next step | Exact phase/assignment to continue and its prerequisite or blocker |

Link the saved records from [orchestration](orchestration.md); state is not a
replacement for them. Keep worker-reported completion separate from the
orchestrator's verified assessment. Save unknown observations as unknown. This
file is a continuation index, not a second execution engine or approval registry.

## Resume after interruption

1. Read `state.md`, the active request and collection plan, then the linked launch,
   result and primary artifacts needed for the remaining work. Check their actual
   existence, content identity, scope and source/configuration basis. A summary
   cannot prove a missing result, successful launch or completed check.
2. Ask the host for the recorded worker's actual state. A saved worker ID or
   `writing_stopped` claim alone does not establish that it is live or stopped.
   Verify the previous writer has stopped before assigning a successor its output;
   an unknown writer state blocks that transfer.
3. Reconcile the current checkout, decisions, configuration and artifacts with
   the saved basis using the rule below. Preserve unavailable artifacts as gaps;
   recover evidence through a bounded assignment instead of reconstructing it
   from conversational claims.
4. Continue a verified live worker only within its phase and bounded problem,
   after revalidating inputs and the completed portion. Changed scope, inputs,
   outputs or limits receive a new saved assignment. A new phase, new group or
   replacement worker receives a fresh context with primary references under
   [context policy](orchestration.md#choose-the-context-boundary).
5. Update state with the verified completed portion, open checks and next step.
   Resume at the earliest affected phase and carry the selected route through its
   final `report.md`. Preserve useful completed work and outstanding limits.

## Reconcile a changed basis

When decisions, sources, configuration or measurement definitions change, identify
the dependent observations, diagnoses, cards and ranking before continuing them.
Retain previous numbered snapshots, analyses, diagnoses and assignment results for
provenance. Mark their applicability in state and the diagnosis index; issue new
affected contributions instead of overwriting their evidence.

| Changed input | Required reassessment |
| --- | --- |
| User decision, required behavior or candidate scope | Revisit affected mechanisms, alternatives, acceptance and cross-card dependencies |
| Source, owner, consumer, wiring or test | Recheck affected source evidence and measurement provenance; collect current identity/evidence where the old basis no longer applies |
| Configuration, source population, mapping or tool definitions | Reconcile the collection plan; recollect/reanalyze affected inputs and compare definitions before comparing values |
| Diagnosis, cards or prerequisite | Reintegrate dependent claims and rerun `rank` for the exact changed cards and snapshot |

Keep an unaffected contribution only after recording why its source, inputs and
decision basis still apply. A local edit can change graph reachability, SCC/PC or
global populations, so the affected set can exceed the changed files. Recollect
or reanalyze the complete relevant graph/population when required by the measure.
Before a ready card refers to the current snapshot, verify its cited declarations,
consumers and evidence against that snapshot. Copying an old `source_state`, or
replacing it with the new value without inspection, does not establish readiness.
If comparability or identity remains unknown, preserve that limit in the claim.

## Explicit focused routes

A focused route requires an explicit task: analyze supplied reports, review a diff
or reassess an implemented recommendation. A bare invocation or general audit
always follows the [full cycle](workflow.md); an existing report alone never
changes that route. For every focused run with a checkout, perform
[configuration maintenance](collection.md#maintain-project-configuration) before
identity capture, even when every measurement is imported.

| Requested route | Entry conditions and phases |
| --- | --- |
| Existing reports with sources | Locate the requested reports and corresponding checkout. Configuration qualifies their scope/provenance; evidence imports suitable inputs and runs `collect`/`analyze`, filling only decision-relevant gaps. Analysis diagnoses the requested groups against matching sources; a fresh architect integrates and delivers through the final-report phase. |
| Source-free reports | Identify supplied artifacts and a destination directory. Configuration records import scope and unknown identities in the report-local configuration/plan; evidence imports and analyzes them. Analysis records hypotheses and bounded questions without claiming source diagnosis. Final report retains those limits; implementation-ready recommendations are unavailable. |
| Diff review | Fix base and target revisions/working states and the requested change. Configuration and evidence establish comparable scopes and separate snapshots; analysis inspects changed contracts and affected consumers, including those outside the diff. Use [reassessment](reassessment.md) and final-report integration for grounded findings. |
| Reassessment | Identify the earlier recommendation, its evidence/acceptance and the implementation to verify. Reconcile configuration and collect current relevant evidence; reuse prior contributions only after basis validation. Analyze acceptance, consequences and dependent recommendations, then deliver a fresh integrated report using [reassessment](reassessment.md). |

Qualify imported artifacts through [collection](collection.md#import-existing-reports):
original source identity, generation provenance, selected population, definitions
and mapping matter. Unknown coverage is not zero. Unknown source identity limits
readiness even when sources are present; source-free calculations cannot establish
current ownership or feasible implementation. A gap never becomes measured merely
because the import or analysis command succeeded.

Use the [phase contracts](workflow.md) for the selected scope, with the same fresh
contexts and exact checks. A narrow request can yield fewer than 8–12 distinct
groups; record that scope bound in the shortlist. Explain phases or measurement
families omitted by the explicit focus. All routes retain requests, results and
evidence in `<report-dir>`, finish with its authored `report.md`, and return that
link. Cards and ranking remain inputs to the report. End with recommendations or
verification findings; implementation requires a separate instruction.
