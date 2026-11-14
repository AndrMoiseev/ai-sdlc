# Architecture audit workflow

Run **configuration → collect → substantive analysis → ranking → final report**.
The orchestrator owns assignments and transitions under
[assignments and context](orchestration.md). Execute assignments sequentially with
fresh contexts at phase and diagnosis-group boundaries. Architects author findings;
explorers research or execute exact checks. Product sources remain read-only.

A bare invocation authorizes the complete audit through `report.md` without extra
approvals between phases. Read [runtime](runtime.md) before producing artifacts.
Save phase and primary links in `state.md`; use [continuation](continuation.md) for
bounded evidence requests or interrupted work. All work refers to current source
paths and task scope. No phase binds the audit to a source version.

## Phase 1: Configuration

**Input:** checkout, requested scope and constraints, existing configuration,
architecture decisions and build/source evidence.

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

1. Start a fresh explorer with a checks assignment containing the registered IDs,
   stage and command-registry revision. Execute existing build/report tasks and
   then `collect` in dependency order. Return tool/report facts to the orchestrator
   for necessary path/configuration updates before a dependent batch.
2. `collect` retains each raw report once, normalizes available inputs, calculates
   all [catalog outputs](measurements.md) in dependency order and saves selections.
   It records errors and missing inputs per chain while completing independent work.
3. Return the compact `collection.json` description, output counts and gaps. Read
   only the JSONL files relevant to the next investigation; do not send the complete
   metric population to the orchestrator.

**Exit:** every planned output is complete or has a concrete unavailable/error reason.
Primary observations, derived values, group aggregates, rankings and threshold
selections are ready before substantive analysis starts. Interrupted calculations
remain incomplete. Source version metadata is neither needed nor inspected.

## Phase 3: Substantive analysis

**Input:** collection description, relevant JSONL records and selections, scope,
current source paths, limitations and known change/behavior scenarios.

1. Start a fresh architect to select 8–12 related candidate groups using
   [Measurements](measurements.md). Merge signals for the same cause; include known
   risks and upcoming changes even without hotspots. Explain a smaller bounded
   population and material omissions. Save the shortlist in `diagnosis.md`.
2. Record each group's source paths/declarations, JSONL paths and object keys,
   scenario, owners, consumers, wiring and tests. A cold dependency can own the cause.
3. Start a fresh architect for each bounded group. Apply the explicit
   [sdd-code-design diagnosis call](diagnosis.md), inspect mechanisms and consumers,
   and save `diagnoses/<group-id>/diagnosis-<n>.md`. Require alternative explanations,
   feasible transformations, required behavior, cost/risk, acceptance and separate
   confidence in observation, diagnosis and effect. Source-free groups stay hypotheses.
4. After group work, start a fresh integration architect. Merge shared causes,
   preserve non-issues and resolve contradictory claims through primary evidence.
   Check dependencies and conflicting transformations across recommendations.
   Apply [Decision output](decision-output.md) to author `cards.json` with readiness
   and grounded M/R/S effects. Request bounded research/checks through the orchestrator
   only when an attainable answer can change the decision.

**Exit:** every shortlisted group has a diagnosis or a specific gap and decision
consequence; authored cards contain the substantive evidence needed for ranking.
A proposed check is not an executed check. Thresholds alone do not establish readiness.

## Phase 4: Ranking

**Input:** authored cards, collection description and current sources.

Assign `rank` to a separate explorer checks assignment. It validates required fields,
current source paths, keyed metric references, effects, boundary acceptance and
prerequisites. Save `ranked-<n>.json` and optional rendered Markdown separately from
`report.md`. Return validation failures to the card author, then rerun ranking on
corrected cards. Preserve equal profiles and separate priority from execution order.

**Exit:** the completed cards have a successful structural ranking result. This
result does not establish the truth of the diagnosis; that belongs to phase 3.

## Phase 5: Final report

**Input:** shortlist, diagnoses, current cards, validated ordering and scope/gaps.

Start a fresh architect to author `report.md` from primary evidence. Show up to
five ready recommendations, their priority rationale, dependencies and acceptance,
the investigation queue and important observations/rejections. Link concrete JSONL
files and object keys, collection description, diagnoses, cards and ranking with
relative paths. Zero ready recommendations is a valid result.

If a substantive contradiction requires changing a card, return it to analysis
and ranking before relying on it in the report. A rendered table alone does not
complete the audit. The orchestrator checks evidence and phase outcomes and returns
the report link with a brief account of recommendations and material limitations.
