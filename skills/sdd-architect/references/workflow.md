# Architecture audit workflow

Run **configuration → collect → substantive analysis → ranking → final report → plan update → project status**.
The orchestrator owns assignments and transitions under
[assignments and context](orchestration.md). Execute assignments sequentially with
fresh contexts at phase and diagnosis-group boundaries. Architects author findings;
explorers research or execute exact checks. Product sources and project settings
remain read-only for every audit participant. Project settings change only in a
separate user-initiated `sdd-setup` process.

A bare invocation authorizes the complete audit and plan update without extra
approvals between phases. Read [runtime](runtime.md) before producing artifacts.
Save phase and primary links in `state.json`; use [continuation](continuation.md) for
bounded evidence requests or interrupted work. All work refers to current source
paths and task scope. No phase binds the audit to a source version.

## Phase 1: Configuration

**Input:** checkout, requested scope and constraints, read-only project settings,
architecture decisions, the current tech debt plan and build/source evidence.

Read the [current plan and relevant cards](tech-debt-plan.md#read-the-plan-before-investigation)
before commissioning research. For fresh collection, first check the project collection settings. Missing or incomplete settings require user-initiated `sdd-setup`. Carry user assessments and known problems into the scope.

1. Start a fresh explorer to research production roots, Gradle projects/variants,
   compiled outputs, the configured measurement scope, exclusions and package
   ownership. Apply [Collection](collection.md), including supplied report inputs.
2. Require proposed configuration and a plan justified by source references.
   Inventory dependencies, history, scc statistics, Kotlin tokens/functions,
   complexity and coverage under [quality indicators](quality-indicators.md). Record exact
   configured command and report paths and known limitations; unknown ownership stays explicit.
3. The orchestrator uses `metrics.py configure` to save project-relative
   `<report-dir>/collection-input.json`, then writes `collection-plan.md` beside it.
   Register executable commands with dependencies, destinations and limits under
   the [checks contract](orchestration.md#register-checks-in-the-collection-plan).
   Earlier audit configurations are research inputs to recheck. Neither role
   changes project settings or treats prior inferred boundaries as user constraints.

**Exit:** saved scope, population, exclusions and module ownership are justified;
the configured project command accounts for every required source. Missing coverage, tools or other prerequisites block the full audit.
Explain the concrete problem and propose resolving it before restarting; do not
silently configure the project's tests or continue with missing sources.

## Phase 2: Collect

**Input:** saved configuration, exact registered commands and output destinations.

Resolve the project [analysis policy](analysis-policy.md) through the script before
running collection. Preserve low detector thresholds used to collect observations.

1. Start a fresh explorer with a checks assignment containing the registered IDs,
   stage and command-registry revision. Execute `collect` once. It runs the project command and imports the outputs.
   Recollection uses a new audit directory with its own configuration.
2. `collect` retains each raw report once, normalizes available inputs, calculates
   all [catalog outputs](measurements.md) in dependency order and saves selections.
   It then [builds candidate groups](candidate-groups.md), attaches contained signals,
   records overlaps and prepares the budgeted investigation queue.
   It also computes project and module aggregates in `metrics/quality-indicators.json`.
   Any failed required source blocks the full audit. The live status remains untouched.
3. Return the path to `collection.json` and the counts from `collect`. Read the
   gap details or keyed JSONL records needed for the next investigation.

**Exit:** every required source and aggregate calculation is complete. A valid
empty population can yield `not_applicable`; a missing source cannot.
Primary observations, derived values, group aggregates, rankings, threshold
selections, preliminary groups and the queue are ready before substantive analysis.
Interrupted calculations remain incomplete. Source version metadata is neither
needed nor inspected.

## Phase 3: Substantive analysis

**Input:** collection description, candidate groups/queue, relevant JSONL records, scope,
current source paths, limitations, existing plan tasks and known change/behavior scenarios.

1. Start a fresh architect to refine the [computed candidate groups](candidate-groups.md).
   Read selected and deferred queue entries, overlaps and limitations. Keep collection
   calculations in the scripts. Inspect sources/context to justify merges, splits,
   additions or omissions, including known risks without hotspots. Save the final
   shortlist in `diagnosis.md` with keyed origins and reasons for each adjustment.
   Match current plan tasks by mechanism and responsibility. Link adequate known
   diagnoses instead of repeating them; retain new problems in the same code area.
2. After shortlist refinement, register the [evidence queries](diagnosis.md#prepare-evidence-for-one-group)
   for the selected origins together in one explorer checks assignment. Pass the
   corresponding saved results to each group architect with the scenario and scope
   adjustments. A cold dependency can own the cause.
3. Start a fresh architect for each bounded group. Apply the explicit
   [sdd-code-design diagnosis call](diagnosis.md), inspect mechanisms and consumers,
   and save `diagnoses/<group-id>/diagnosis-<n>.md`. Require alternative explanations,
   evidenced directions, required behavior, cost/risk, observable effect criteria and separate
   confidence in observation, diagnosis and effect. Source-free groups stay hypotheses.
4. After group work, start a fresh integration architect. Merge shared causes,
   preserve non-issues and resolve contradictory claims through primary evidence.
   Check dependencies and conflicting directions across recommendations.
   Apply [Decision output](decision-output.md) to author six-section Markdown cards
   in `recommendations/` and compact `cards.json` metadata with readiness and grounded
   M/R/C effects. Keep detailed design questions for human-involved `sdd-spec` work.
   Request bounded research/checks through the orchestrator
   only when an attainable answer can change the decision.

**Exit:** every shortlisted group has a diagnosis or a specific gap and decision
consequence; authored cards contain the substantive evidence needed for ranking.
A proposed check is not an executed check. Thresholds alone do not establish readiness.

## Phase 4: Ranking

**Input:** authored cards, collection description and current sources.

Assign `rank` to a separate explorer checks assignment. It validates compact metadata,
the six-section Markdown structure, current source paths, keyed metric references
and effects. Save `ranked-<n>.json` and optional rendered Markdown separately from
`report.md`. Return validation failures to the card author, then rerun ranking on
corrected cards. Preserve equal profiles; leave implementation planning to `sdd-spec`.

**Exit:** the completed cards have a successful structural ranking result. This
result does not establish the truth of the diagnosis; that belongs to phase 3.

## Phase 5: Final report

**Input:** shortlist, diagnoses, current cards, validated ordering and scope/gaps.

Start a fresh architect to author `report.md` from primary evidence. Obtain the
saved collection policy through the script and show ready directions within
`recommendations.report_limit`, their priority rationale, dependencies and effect criteria,
the investigation queue and all `observe`/`rejected` cards. Link concrete JSONL
files and object keys, collection description, diagnoses, cards and ranking with
relative paths. Link each full six-section card instead of duplicating its narrative.
Zero ready recommendations is a valid result. The report supports subsequent
discussion with a human in `sdd-spec`; it does not start that workflow.

If a substantive contradiction requires changing a card, return it to analysis
and ranking before relying on it in the report. A rendered table alone does not
complete the audit. The orchestrator checks evidence and phase outcomes before
updating the plan.

## Phase 6: Plan update

**Input:** report, complete validated card set and the latest user-edited plan.

The orchestrator applies [plan maintenance](tech-debt-plan.md), adding only new
`ready` and `needs_check` tasks and retaining existing cards and user decisions.
Read the plan again before writing; place every ready task before every needs-check
task. Record additions, reused tasks and disagreements in the report and completion
state. No eligible additions is a valid result and still requires the final notification.

**Exit:** plan cards and table agree, links resolve, repeated completion creates no
duplicates. All substantive audit work is complete before publishing project status.

## Phase 7: Project status and delivery

**Input:** successful full collection, finished report and updated plan.

The orchestrator verifies that all preceding phases succeeded, saves
`phase: publication` and its pending assignment in `state.json`, and assigns
the final `metrics.py status --collection <report-dir>/collection.json`
under the checks contract. The command replaces `memory/tech-debt/status.json` and
renders `status.md` from that JSON structure. It also copies the bundled indicator
guide beside the report for readers. Keep the guide out of every agent's context.
This is the last audit phase;
see [publication](quality-indicators.md#publication). After verifying its result and
the writer's stop, record the accepted handoff and `phase: complete` in `state.json`,
clear finished work and run the continuation-state check. Interrupted or failed
publication leaves the audit unfinished.

If any earlier phase fails or is interrupted, stop without touching the previous
status. A failure during the final writes requires no rollback, backup or
recovery protocol; earlier committed values remain in Git.

**Exit:** the final response links report, plan and status. Notify the user about
all excluded card statuses, including when `observe` and `rejected` are both absent.
