# Stratified Design

Use this reference when domain operations expose storage or transport details,
or when comparing boundaries intended to localize policy and representation
changes. Start with the selected operation, its actual callers and the required
behavior.

## Identify the semantic layers

A semantic layer provides a language for one level of meaning: its values and
operations, ways to combine them, and abstractions that hide their implementation.
An operation at one level can become a primitive at the next. For example, parsing
stored fields produces a reservation; operations on reservations express a booking
decision. The caller should understand that decision without reconstructing the
storage format.

Name the concepts used by the selected operation. Identify where a caller must
switch from a domain decision to an implementation detail. Inspect the contract
that could hide that detail, including an existing operation that already owns it.
A different name for the same exposed details does not establish a useful boundary.

One module can contain several semantic layers, and one layer can span modules.
Choose boundaries from the work callers need to perform. File count, graph depth
and the number of helpers do not establish their usefulness. Keep a cohesive
operation intact when another boundary would only add navigation.

## Compare two kinds of change

For a disputed boundary, choose a plausible business-rule change and a plausible
data-representation change. Use a supplied upcoming change when available; label
constructed scenarios as hypothetical. If one kind has no plausible scenario in
the inspected scope, state that limit instead of inventing work to complete a pair.

| Change | What to trace |
| --- | --- |
| Business rule | Which decision, invariant owner, callers and behavior tests must change? |
| Data representation | Which parser, adapter, callers and contract tests must change while the domain meaning stays fixed? |

For each applicable scenario:

1. Trace the current construction through its actual consumers and tests. Name
   the implementation knowledge that crosses the candidate boundary.
2. Compare it with the smallest useful change, reusing an existing boundary when
   it already owns the responsibility. State which declarations and consumers
   would change and which knowledge they would need afterward.
3. Explain whether the proposal localizes the change, merely moves work to another
   consumer, or introduces a new obligation. Retaining the current construction
   is a valid result; fewer changed files alone does not establish an improvement.
4. State an acceptance check for the claimed isolation and required behavior.
   Keep proposed checks distinct from checks already performed.

Put this comparison in the existing diagnosis or design options. It needs no
separate report or mandatory diagram. When interface obligations change, use the
[consumer-obligation comparison](rules.md#11-compare-consumer-obligations-before-and-after).
Project requirements determine whether an interface or format must remain
compatible; a representation-change scenario does not add that requirement.

## Example: booking policy and stored timestamps

Suppose a booking operation parses a stored timestamp and checks the maximum
party size. Compare raising the permitted party size with replacing the stored
timestamp text by epoch seconds while keeping its time meaning unchanged.

If callers perform both parsing and policy checks, both changes may require them
to understand storage fields. An existing parser can own the timestamp conversion
and return a valid reservation; a policy operation can own the party-size rule.
The representation change then belongs to the parser and its contract tests,
while the rule change belongs to the policy and its behavior tests. Inspect the
callers to establish that they actually use these boundaries.

This separation is useful when it removes concrete knowledge or repeated work
from consumers. A small cohesive operation with no such burden may need no new
helper, type or module.

## Keep semantic level and effects separate

Semantic level describes the concepts an operation exposes. Purity describes
whether it computes from explicit inputs without effects or time-dependent reads.
Pure functions can still mix unrelated levels; effectful operations such as
delivery and acknowledgement can have useful semantic boundaries.

For a proposed pure pipeline, check the distinction between CQS queries and pure
transformations in [Sequential Composition](patterns.md#pattern-sequential-composition).
When extracting calculations moves a read, write or resource boundary, apply
[Preserve behavior when moving effects](patterns.md#preserve-behavior-when-moving-effects)
before accepting the new structure.
