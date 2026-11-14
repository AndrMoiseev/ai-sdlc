# Recommendation cards and priority

Prepare directions and evidence for a human to develop through `sdd-spec`.
The report lets the reader judge which refactoring direction deserves
that work; delivery also includes [plan maintenance](tech-debt-plan.md).
A ready recommendation is sufficiently grounded for that discussion;
it is not an approved design or an implementation plan.

The fresh integration architect owns this work in the
[analysis phase](workflow.md#phase-3-substantive-analysis). Reconcile bounded
diagnoses, merge shared causes, preserve important non-issues and resolve
contradictions through primary evidence before writing cards.

## Author cards

Copy [the Markdown template](../assets/recommendations.example.md) to
`<report-dir>/recommendations/<id>.md` for each card. Write in the user's language.
Keep the six numbered level-two headings in this order, with substantive content
under each. The title names the direction. These are the card's six sections:

| Section | Required content |
| --- | --- |
| 1. What is the problem and where does it appear? | The observed construction, affected area, representative change or behavior scenario and consequence. Distinguish real and hypothetical scenarios. |
| 2. What supports it? | Inspected source paths and declarations, consumers, wiring, tests, relevant history and keyed measurement references. Explain findings, measurement suitability and limitations; distinguish inspected facts from assumptions. |
| 3. How does the problem arise? | The causal mechanism, existing protection, an alternative explanation and what checking it established. Retain the applicable diagnostic heuristic's file/section. State confidence in the observation and diagnosis separately. |
| 4. Which direction is proposed? | The intended change in responsibility or dependency, its owner and affected consumers. Use a current/proposed diagram when it clarifies the direction; label the proposal and unresolved choices. Keep future packages, types and API details for `sdd-spec`. |
| 5. Why is it worth developing? | Expected M/R/S effects and their grounds, confidence in those predictions, material costs, risks and dependencies, and comparison with keeping the current system or a smaller intervention. Explain the recommendation's priority. |
| 6. What remains for `sdd-spec`? | Open design questions, required behavior and observable signs of achieving the effect. Distinguish questions that could overturn the direction from choices about its implementation. For unresolved or deferred cards, name the next discriminating check or revisit trigger. |

Exact references to existing declarations establish the diagnosis. They do not
require designing future declarations. Describe a desired boundary through its
responsibility and dependency direction. Detailed contracts, task sequences,
test implementations and ArchUnit rule/import-scope design belong to the later
human-involved `sdd-spec` work.

Investigate an attainable answer that could change the direction. If a material
question remains, use `needs_check` and explain the question, next check and how
each outcome affects the recommendation. An implementation choice that does not
change the direction can remain open in a `ready` card. For `observe` or `rejected`,
explain the disposition and meaningful revisit condition in the same six sections;
do not invent a problem or an effect to fill the template.

In section 2, address measurements by relative JSONL path and complete object key,
not line number. Explain units, population, relevant counters, thresholds and
shared provenance where needed to interpret the claim. Cards describe current
sources without source-version fields. Keep costs as a supported range or unknown.
Resolve Markdown links from the card's own directory. Measurement addresses in
metadata remain relative to the collection's report directory.

## Judge effects and readiness

Use this ordinal profile relative to the current system:

| Category | Modularity | Regression risk reduction | Development speed |
| --- | --- | --- | --- |
| substantial | Removes established coordinated changes across independent responsibilities or a significant implementation leak | Closes a significant concrete regression mechanism | Removes recurring coordination/manual work/wait in a representative task |
| local | Makes one responsibility or contract more independent in a bounded scenario | Closes a local behavioral protection gap | Simplifies a bounded part of the change/check |
| not_shown | No demonstrated improvement | No demonstrated reduction | No demonstrated acceleration |

An effect is a grounded prediction, not a measured outcome of future work.
Keep `unknown` and `worsening` explicit in unresolved recommendations; do not rank
them as ready by substituting `not_shown`. Resolve material trade-offs before
assigning one category. Speed judgments remain qualitative. Several derivatives
of one measurement do not independently establish an effect.

Before setting `ready`, check that the six sections establish a consequential
problem, its mechanism, an evidence-backed direction with at least one benefit,
required behavior and the remaining design questions. A metric threshold alone
cannot establish readiness. Final design and implementation authorization remain
with the human-involved follow-up.

## Check and rank

Use [the metadata example](../assets/recommendations.example.json) for
`<report-dir>/cards.json`. This is a small input to `rank`, not the card text.
Each entry contains only:

- `id`, `status` and `card`: the Markdown path relative to `cards.json`.
- `source_evidence`: inspected `file` and `declaration` addresses; their explanation
  lives in section 2. A ready card needs at least one inspected source reference.
- `metric_evidence`: relative JSONL `path` and complete `key`; interpretation lives
  in section 2. An empty list is valid for a source-grounded issue without a metric.
- `effects`: the three M/R/S categories, required for ready recommendations.

Keep the explanations and diagrams in the Markdown card. Match every metadata
address and effect to the card; do not copy narrative fields into JSON.

The orchestrator assigns `rank` to explorer through the shared checks contract.
It checks metadata, the six-section Markdown structure, current source paths,
keyed measurement references and effect categories. It sorts ready profiles
lexicographically M→R→S and preserves equal-profile priority groups. It produces
no implementation order. The integration architect checks meaning, duplicate
causes, evidence correspondence and cross-recommendation conflicts; the script
cannot establish those judgments. Return failures to that author and rerun after
changes to cards or metadata.

## Deliver the report

Show up to five ready recommendations in a table: priority group, direction,
M/R/S effects, basis/confidence and material cost/dependencies. Link each to its
complete six-section Markdown card. Within this audit keep the full card in one place; use summaries
and links in `report.md`, followed by the short investigation queue and a linked
list of every `observe` and `rejected` card with its reason. Zero ready recommendations
is a valid result. The five-direction display limit does not limit plan admission:
all new `ready` and `needs_check` cards are eligible.

State the inspected scope and material gaps. Link the collection description,
specific JSONL records, diagnoses and ranking with paths relative to the report.
For every strict priority difference explain “above the next because …” through
the scenario and M/R/S order. Equal effects stay tied. Costs and dependencies
inform the human's next choice; they are not a task sequence or a scalar tie-breaker.

Save generated ranking Markdown separately from `report.md`. A fresh architect
authors the final report, preserving validated order and uncertainty. The report
and linked cards provide the evidence for subsequent `sdd-spec` discussion;
completing the audit does not start that workflow. The orchestrator then updates
the plan under its separate contract and returns both links, additions/known tasks,
limitations and explicit notification of the excluded statuses. Audit ranking does
not overwrite the user's current assessment or priority in the plan.
