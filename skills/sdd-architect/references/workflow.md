# Architecture audit workflow

Run **configuration → collect → substantive analysis → ranking → final report → plan update**.
The orchestrator owns assignments and transitions under
[assignments and context](orchestration.md). Execute assignments sequentially with
fresh contexts at phase and diagnosis-group boundaries. Architects author findings;
explorers research or execute exact checks. Product sources remain read-only.

A bare invocation authorizes the complete audit and plan update without extra
approvals between phases. Read [runtime](runtime.md) before producing artifacts.
Save phase and primary links in `state.md`; use [continuation](continuation.md) for
bounded evidence requests or interrupted work. All work refers to current source
paths and task scope. No phase binds the audit to a source version.

## Phase 1: Configuration

**Input:** checkout, requested scope and constraints, existing configuration,
architecture decisions, the current tech debt plan and build/source evidence.

Read the [current plan and relevant cards](tech-debt-plan.md#read-the-plan-before-investigation)
before commissioning research. Carry user assessments and known problems into the scope.

1. Start a fresh explorer to research production roots, Gradle projects/variants,
   compiled outputs, existing measurement and test tasks, exclusions and package
   ownership. Apply [Collection](collection.md), including supplied report inputs.
2. Require proposed configuration and a plan justified by source references.
   Inventory dependencies, history, size, complexity and coverage. Record exact
   commands or input paths and known limitations; unknown ownership stays explicit.
3. The orchestrator saves `.sdd/architect/collection.json` and `collection-plan.md`.
   Register executable commands with dependencies, destinations and limits under
   the [checks contract](orchestration.md#register-checks-in-the-collection-plan).
   Explorer proposes changes but does not edit project configuration or settings.

**Exit:** saved scope, population, exclusions and ownership are justified; every
measurement family has an intended source or a concrete gap.

## Phase 2: Collect

**Input:** saved configuration, exact registered commands and output destinations.

Resolve the project [analysis policy](analysis-policy.md) through the script before
running collection. Preserve low detector thresholds used to collect observations.

1. Start a fresh explorer with a checks assignment containing the registered IDs,
   stage and command-registry revision. Execute existing build/report tasks and
   then `collect` in dependency order. Return tool/report facts to the orchestrator
   for necessary path/configuration updates before a dependent batch.
2. `collect` retains each raw report once, normalizes available inputs, calculates
   all [catalog outputs](measurements.md) in dependency order and saves selections.
   It then [builds candidate groups](candidate-groups.md), attaches contained signals,
   records overlaps and prepares the budgeted investigation queue.
   It records errors and missing inputs per chain while completing independent work.
3. Return the compact `collection.json` description, output counts and gaps. Read
   only the JSONL files relevant to the next investigation; do not send the complete
   metric population to the orchestrator.

**Exit:** every planned output is complete or has a concrete unavailable/error reason.
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
2. Record each group's source paths/declarations, JSONL paths and object keys,
   scenario, owners, consumers, wiring and tests. A cold dependency can own the cause.
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

## Phase 6: Plan update and delivery

**Input:** report, complete validated card set and the latest user-edited plan.

The orchestrator applies [plan maintenance](tech-debt-plan.md), adding only new
`ready` and `needs_check` tasks and retaining existing cards and user decisions.
Read the plan again before writing; place every ready task before every needs-check
task. Record additions, reused tasks and disagreements in the report and completion
state. No eligible additions is a valid result and still requires the final notification.

**Exit:** plan cards and table agree, links resolve, repeated completion creates no
duplicates, and the final response links both report and plan. Notify the user about
all excluded statuses, including when `observe` and `rejected` are both absent.
