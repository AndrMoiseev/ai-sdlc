# Focused code diagnosis

Diagnose a selected candidate for a refactoring decision: a hotspot, a related
group of declarations, or an area selected for a known risk or upcoming change.
Return findings grounded in source code. The caller owns candidate selection,
architectural effect judgments and priority across recommendations.

This route is read-only. End with the diagnosis; implementation, persistent gates
and project-instruction edits require their own task. A selected candidate does
not start the full PR-review workflow or a repository-wide rule audit.

## Table of Contents

- [Establish the input and scope](#establish-the-input-and-scope)
- [Inspect the common questions, then select rules](#inspect-the-common-questions-then-select-rules)
- [Establish a consequential finding](#establish-a-consequential-finding)
- [Return the diagnosis](#return-the-diagnosis)

## Establish the input and scope

Recover these inputs from the calling skill or the user's explicit request:

- Candidate paths, declarations and source revision/working state.
- Reason for selection: supplied metric signals, an incident, a critical contract
  or a planned change. Metrics may be absent.
- The change or behavior scenario, required product behavior and known constraints.
- Available measurements with their scope and limitations, relevant history and
  existing evidence about consumers, wiring and tests.

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

## Inspect the common questions, then select rules

For every candidate, inspect three questions even when its selecting metric
concerns something else:

1. Can a caller misuse the contract while still satisfying its types, for example
   by swapping primitive identifiers with different domain meanings?
2. Who enforces each relevant invariant, and can construction or a consumer bypass
   that protection?
3. Which implementation knowledge, dependencies and side effects must a consumer
   account for when making the representative change?

Use observed code features to select one primary reference and at most one or two
secondary references. The table supplies starting points, not mandatory checks
for every candidate. Select language examples through [guidelines](../guidelines.md)
only when needed to establish a feasible option.

| Observation | Question to investigate | Reference |
| --- | --- | --- |
| Branching, interacting state or mixed responsibilities | Which reasons for change and effects are entangled? | [Decomposition rules](../references/decomposition/rules.md), [smells](../references/decomposition/smells.md) |
| Coordinated edits across responsibilities | Which rule or implementation detail has multiple owners or leaks to consumers? | [Decomposition smells](../references/decomposition/smells.md), [encapsulation](../references/encapsulation/rules.md) |
| Interchangeable primitive parameters or implicit contract conditions | Which misuse is representable, and where would stronger types actually prevent it? | [API design](../references/api-design/rules.md), [encapsulation](../references/encapsulation/rules.md) |
| Repeated or bypassed validation | Where should validity be established and maintained? | [Encapsulation](../references/encapsulation/rules.md) |
| Hidden effects or infrastructure mixed with domain decisions | Which effects surprise consumers or force unrelated changes? | [API design](../references/api-design/rules.md), [separation of concerns](../references/separation-of-concerns/rules.md) |
| Existing tests appear to miss the concrete failure | Which assertion or invariant would distinguish correct and incorrect behavior? | [Outside-in testing](../references/outside-in-tdd/rules.md) |

Preserve supplied measurements and their qualification. Heuristic thresholds in
references do not redefine the caller's measurements or trigger another collection
run. Request an additional check only when its attainable answer changes the
diagnosis or the choice of transformation.

## Establish a consequential finding

For each suspected problem:

1. Locate the observed construction and cite the rule's file and section. Explain
   why the rule applies in this context, including relevant exceptions.
2. Trace the scenario through the code to a concrete error, coordinated edit,
   hidden dependency or repeated work. Inspect existing protection and an
   alternative explanation before calling it a problem.
3. Compare the current construction with the smallest useful transformation.
   Identify changed declarations, responsibility/contract ownership, consumers,
   preserved behavior, cost drivers and intervention risks. Retaining the current
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

Start with the candidate, source identity, selection reason and inspected scope,
including any cold dependencies and important omissions. Return a compact finding
for each distinct cause with:

- **Evidence and rule:** exact paths and declarations, observed construction,
  relevant consumers/tests, and the heuristic reference and section.
- **Scenario and mechanism:** the consequence, existing protection, alternative
  explanation examined and what the inspection established.
- **Options:** current construction, smallest useful change, affected owner and
  consumers, expected effect, cost drivers and intervention risks.
- **Acceptance:** the check that would establish the effect and preserve required
  behavior; identify proposed checks that have not run.
- **Uncertainty:** confidence in observation, diagnosis and expected effect
  separately; any consequential question, accessible next check and how its
  possible answers change the decision.

Retain important non-issues with their explanation and unresolved questions with
their limits. Zero justified findings is a completed diagnosis; do not widen the
search merely to fill a quota. The result covers only the inspected scope.

Return to the caller for deduplication, recommendation readiness and prioritization.
When invoked directly, deliver the same bounded diagnosis to the user without
assigning a project-wide priority or starting implementation.
