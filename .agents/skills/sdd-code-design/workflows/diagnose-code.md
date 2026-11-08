# Focused diagnosis

Diagnose a selected proposed design or implemented code: a contract, a related
group of responsibilities, or an area selected for a known risk or upcoming change.
Ground findings in the named work product. The caller owns scope, architectural
effect judgments and priority across recommendations.

This route is read-only. End with the diagnosis; implementation, persistent gates
and project-instruction edits require their own task. A selected candidate does
not start the full PR-review workflow or a repository-wide rule audit.
The caller's lens boundaries, report format, check-execution limits, severity and
acceptance policy govern the return. Send observations outside the assigned lens
to the caller with their intended owner; they are not extra verdicts.

## Table of Contents

- [Establish the input and scope](#establish-the-input-and-scope)
- [Inspect the selected work product](#inspect-the-selected-work-product)
- [Inspect the common questions, then select rules](#inspect-the-common-questions-then-select-rules)
- [Establish a consequential finding](#establish-a-consequential-finding)
- [Return the diagnosis](#return-the-diagnosis)

## Establish the input and scope

Recover these inputs from the calling skill or the user's explicit request:

- Work product: **proposed design** or **implemented code**; candidate paths,
  document sections or declarations, and revision/working state.
- Reason for selection: supplied metric signals, an incident, a critical contract
  or a planned change. Metrics may be absent.
- The change or behavior scenario, required product behavior and known constraints.
- Available measurements with their scope and limitations, relevant history,
  accepted requirements and evidence about consumers, wiring and tests.

For **refactoring**, also recover the current and target structure, the declared
preservation boundary, original behavior sources and proposed or approved test
changes. In SDD these come from proposal/design and tasks when present; assess
`result` and `preservation` separately without requiring specs or new REQ IDs.
For a task candidate, distinguish its local acceptance and contribution from
whole-result criteria and later transition stages. Use the original baseline to
assess preservation claims; newly green tests alone do not establish prior behavior.

## Inspect the selected work product

For **implemented code**, use source inspection:

Read the selected declarations in full and inspect the consumers, invariant owners,
wiring and tests needed to explain the scenario. Inspect representative commits
when history motivates selection; distinguish substantive changes from formatting,
generation or mechanical rewrites. A frequently changed file is not itself proof
of a defect or poor design.

Expand into a cold dependency when it may own the cause. Record why each expansion
is needed and stop expanding when the mechanism and affected consumers are clear.
Keep uninspected areas and unavailable evidence explicit. Without source access,
return questions and limits; do not invent source findings. If no scenario was
supplied, derive an explicitly hypothetical one from the inspected code.

For **proposed design**, read the requirements and the selected design's contracts,
responsibilities, dependency direction, operations and proposed checks. Trace a
scenario through the explicitly described construction. Existing code and tests
can establish the current baseline or integration constraints; cite them separately
from claims about the proposal. Future code and test execution are not prerequisites
for identifying a contradiction in the design.

Distinguish three conclusions:

- **Design defect:** an explicit choice permits a concrete violation or contradicts
  another required property. Cite the choice, requirement and failure mechanism.
- **Material gap:** an unspecified choice prevents assessing an important guarantee
  or selecting a boundary. State which decision depends on it and what would resolve it.
- **Implementation freedom:** a detail can be decided later without changing the
  required guarantee or boundary. Its omission is not a finding.

For example, a design that sends confirmation before saving contradicts a requirement
that a failed save sends no confirmation. Unspecified ordering is a material gap
when that guarantee depends on it. A helper's unspecified name can remain an
implementation choice. Proposed tests remain proposed; the diagnosis establishes
neither runtime behavior nor conformance of code that has not been inspected.
When existing source is unavailable, qualify the affected baseline claim without
discarding conclusions supported by the design itself.

## Inspect the common questions, then select rules

For every candidate, inspect three questions even when its selecting metric
concerns something else:

1. Can a caller misuse the contract while still satisfying its types, for example
   by swapping primitive identifiers with different domain meanings?
2. Who enforces each relevant invariant, and can construction or a consumer bypass
   that protection?
3. Which implementation knowledge, dependencies and side effects must a consumer
   account for when making the representative change? For a proposed interface
   change, apply the [consumer-obligation comparison](../references/decomposition/rules.md#11-compare-consumer-obligations-before-and-after).

Use inspected code or explicitly proposed constructions to select one primary reference and at most one or two
secondary references. The table supplies starting points, not mandatory checks
for every candidate. Select language examples through [guidelines](../guidelines.md)
only when needed to establish a feasible option.

| Observation | Question to investigate | Reference |
| --- | --- | --- |
| Branching, interacting state or mixed responsibilities | Which reasons for change and effects are entangled? | [Decomposition rules](../references/decomposition/rules.md), [smells](../references/decomposition/smells.md) |
| Coordinated edits across responsibilities | Which rule or implementation detail has multiple owners or leaks to consumers? | [Decomposition smells](../references/decomposition/smells.md), [encapsulation](../references/encapsulation/rules.md) |
| Domain operations expose storage or transport representation | Would a business-rule change and a representation change affect different owners and consumers? | [Stratified Design](../references/decomposition/stratified-design.md) |
| Forwarding chains or suspected redundant abstractions | What disappears, moves to consumers or loses an owner if the abstraction is removed? | [Hypothetical removal](../references/decomposition/rules.md#12-mentally-remove-a-suspected-indirection) |
| Interchangeable primitive parameters or implicit contract conditions | Which misuse is representable, and where would stronger types actually prevent it? | [API design](../references/api-design/rules.md), [encapsulation](../references/encapsulation/rules.md) |
| Repeated or bypassed validation | Where should validity be established and maintained? | [Encapsulation](../references/encapsulation/rules.md) |
| Hidden effects or infrastructure mixed with domain decisions | Which effects surprise consumers or force unrelated changes? | [API design](../references/api-design/rules.md), [separation of concerns](../references/separation-of-concerns/rules.md) |
| A proposed extraction moves reads, writes or resource boundaries | Which required ordering, failure handling or resource lifetime could change? | [Preserve behavior when moving effects](../references/decomposition/patterns.md#preserve-behavior-when-moving-effects) |
| Existing tests appear to miss the concrete failure | Which assertion or invariant would distinguish correct and incorrect behavior? | [Outside-in testing](../references/outside-in-tdd/rules.md) |

Preserve supplied measurements and their qualification. Heuristic thresholds in
references do not redefine the caller's measurements or trigger another collection
run. Request an additional check only when its attainable answer changes the
diagnosis or the choice of transformation.

## Establish a consequential finding

For each suspected problem:

1. Locate the observed or proposed construction and cite the rule's file and section. Explain
   why the rule applies in this context, including relevant exceptions.
2. Trace the scenario through the code or described design to a concrete error, coordinated edit,
   hidden dependency or repeated work. Inspect existing protection and an
   alternative explanation before calling it a problem.
3. Compare the inspected construction with the smallest useful alternative.
   Identify changed declarations, responsibility/contract ownership, consumers,
   required behavior, cost drivers and intervention risks. Retaining the inspected
   construction is a valid result.
4. State an acceptance check that discriminates the claimed improvement. Separate
   checks already performed from proposed checks and predicted effects.

A rule deviation alone does not justify a finding. Do not count deviations as a
quality score or infer regression probability, time savings or priority from them.
Respect project requirements; compatibility work is additional scope only when
explicitly required.

For distinct domain identifiers, distinguish rejection of an already typed value
of the wrong kind from correct parsing of raw values, validity of those values and
mix-ups between values of the same type. Verify the language mechanism: a type
alias may leave the unwanted substitution possible. A stronger contract can have
a useful acceptance check while graph or complexity metrics remain unchanged.

## Return the diagnosis

Start with the work product, candidate, source identity, selection reason and inspected scope,
including any cold dependencies and important omissions. Return a compact finding
for each distinct cause with:

- **Evidence and rule:** exact paths and document sections or declarations, inspected construction,
  relevant consumers/tests, and the heuristic reference and section.
- **Scenario and mechanism:** the consequence, existing protection, alternative
  explanation examined and what the inspection established.
- **Options:** current construction, smallest useful change, affected owner and
  consumers, expected effect, cost drivers and intervention risks. Include applicable
  consumer-obligation comparisons and hypothetical-removal outcomes.
- **Acceptance:** the check that would establish the effect and preserve required
  behavior; identify proposed checks that have not run.
- **Uncertainty:** confidence in observation, diagnosis and expected effect
  separately; any consequential question, accessible next check and how its
  possible answers change the decision.

For proposed design, retain the distinction between a design defect, material gap
and implementation freedom in the caller's existing finding or limitation fields.
Use its completion rules when a material gap prevents a required conclusion.

Retain important non-issues with their explanation and unresolved questions with
their limits. Zero justified findings is a completed diagnosis; do not widen the
search merely to fill a quota. The result covers only the inspected scope.

Return to the caller for deduplication, recommendation readiness and prioritization.
When invoked directly, deliver the same bounded diagnosis to the user without
assigning a project-wide priority or starting implementation.
