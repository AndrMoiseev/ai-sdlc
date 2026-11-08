# Recommendation cards and priority

Separate the investigation queue from implementation priority. Metrics and
thresholds explain why a candidate was examined. Only an established mechanism
and a feasible transformation justify an effect category.

The fresh integration architect owns this work in the
[final-report phase](workflow.md#phase-4-final-report). It reconciles bounded
diagnoses, resolves shared causes and contradictions, and checks dependencies
across the whole recommendation set before authoring cards.

Use this ordinal profile relative to the current system:

| Category | Modularity | Regression risk reduction | Development speed |
| --- | --- | --- | --- |
| substantial | Removes established coordinated changes across independent responsibilities or a significant implementation leak | Closes a significant concrete regression mechanism | Removes recurring coordination/manual work/wait in a representative task |
| local | Makes one responsibility or contract more independent in a bounded scenario | Closes a local behavioral protection gap | Simplifies a bounded part of the change/check |
| not_shown | No demonstrated improvement | No demonstrated reduction | No demonstrated acceleration |

Keep `unknown` and `worsening` explicit in unresolved cards. They cannot be ranked
as ready by substituting not_shown. Mixed modularity gains/losses require a decision
before assigning one category. Speed claims remain qualitative: no hours saved or
percent acceleration is calculated from churn, PC or coverage.

## Author cards

Copy [recommendations.example.json](../assets/recommendations.example.json) to
`<report-dir>/cards.json` and replace every example. `revision` and `source_state`
come from the snapshot. Required ready-card fields are:

- `id`, `status: "ready"`, `cause`, `action` with exact source objects and owner.
- `source_evidence`: inspected snapshot file, declaration including signature, and
  finding; include relevant consumers, wiring and tests in the narrative evidence.
- `metric_evidence`: records, values/units, numerators/denominators, aggregation,
  thresholds, suitability, M/R/S weights and shared provenance groups. Use an
  empty list only for a source-grounded issue unsupported by a measured signal.
- `scenario`, `mechanism`, `alternative_explanation` and the observed outcome of
  checking it; distinguish facts from a hypothetical future scenario. In
  `mechanism`, retain the diagnostic heuristic's file/section and explain its
  applicability; the rule reference does not replace inspected source evidence.
- `baseline`, `chosen_option`, responsibility/contract/dependency before/after,
  concrete consumers, and why the smaller or no-change option was not selected.
- `effects` for modularity, regression_risk and development_speed, plus
  `expected_effect` explaining each category and what is still a prediction.
- `confidence` separately for observation, diagnosis and effect, with grounds.
- `steps`, `cost_and_risk`, `acceptance`, `revisit`, `priority_reason`.
- `feasible: true`, `preserves_required_behavior: true`, `depends_on` IDs.
- `boundary_change`; if true, `boundary` with packages, responsibility,
  public_contract, allowed_dependencies, archunit_rule, import_scope,
  forbidden_dependency and allowed_example.

Unresolved cards use `status: "needs_check"`, `question`, `next_action`,
`decision_if_yes` and `decision_if_no`. Observation/rejection cards use `reason`
and `revisit`. Keep costs as a supported range or unknown, never invented days.

The orchestrator assigns `rank` to explorer through the shared checks contract,
using the exact cards and snapshot as its basis. Explorer returns command outcomes
and full artifact references. The integration architect assesses failures and
changes the cards; a changed input requires new assigned check evidence.

`rank` checks completeness, source identity, duplicate causes, effect categories,
boundary acceptance and prerequisite cycles. It sorts ready profiles
lexicographically M→R→S and emits equal-profile priority groups. It cannot verify
that the source evidence was honestly inspected or that a semantic diagnosis is
correct; review those before invoking it.

## Deliver a decision

Show up to five ready recommendations in a table: priority group, concrete change,
M/R/S effects, basis/confidence, cost/dependencies. Follow with their compact cards,
the short investigation queue, observations and important rejections. Zero ready
recommendations is a valid result. Save the finished report as `<report-dir>/report.md`
and link the snapshot, analysis, diagnosis notes and authored cards with relative
paths. State the inspected scope and material collection/diagnosis gaps, preserving
the source references behind each recommendation. The orchestrator replies with
the report link and a brief summary of the recommendations.

For every strict priority difference state “above the next because …”, referring
to the scenario and value order. Equal effects remain tied; explain effort,
intervention risk, prerequisites and historical exposure as execution considerations.
Do not assign an artificial scalar score to break a tie.

Hotspot position and the number of heuristic deviations are investigation context,
not an implementation ranking. A stronger type contract may reduce regression
risk without changing graph/complexity metrics or demonstrating better modularity;
assign only the effects established for its scenario.

Remove duplicate recommendations for the same cause or identify alternatives and
select one. Preparation tests belong to their parent change. A lower-priority
prerequisite can execute earlier without acquiring its parent's benefit; the
script emits execution order separately from priority. If the first five cards
depend on another card, include that prerequisite explicitly in their preparation
and link its retained JSON card.

Save generated Markdown separately from `report.md`; the integration architect
authors the final report after receiving the ranking result. The Markdown renderer
is a mechanical starting point. Render lists and citations
legibly in the user's language, preserving the validated order, all critical
conditions and uncertainty. Do not replace measured values while editing prose.
