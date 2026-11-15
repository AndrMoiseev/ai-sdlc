# From a candidate to an evidenced refactoring direction

## Request focused code diagnosis

Follow the analysis and final-report phases in the [workflow](workflow.md).
The orchestrator owns the investigation queue and gives an architect one bounded
candidate-group assignment. The assigned architect explicitly loads
[sdd-code-design](../../sdd-code-design/SKILL.md) and selects its
[focused code diagnosis](../../sdd-code-design/workflows/diagnose-code.md) route.
Apply it to that source-available group, including owners, consumers, wiring and
tests needed to explain the mechanism across package or module boundaries.
The sibling paths are relative to this reference; from the `sdd-architect` skill
directory the entry point is `../sdd-code-design/SKILL.md`. Resolve the loaded
skill's own references from its directory. This is an explicit file-based call;
it does not rely on automatic skill selection or the Skill tool.

For this architecture audit, apply the focused route's input-basis requirement
using the current checkout path, declarations and task scope only. Its generic
request for revision/working state does not apply here: omit those fields and
all version comparisons from the assignment and result. Keep this instruction
in the bounded diagnosis request so loading the shared route cannot introduce
source-version checks into the audit.

Pass the computed candidate-group path/key (or the reason for a contextual addition),
the architect's scope adjustment, current paths/declarations, task scope, selection
reason, JSONL metric paths and object keys, limitations, known change/behavior scenario,
required behavior and relevant source/history evidence. Use a source-grounded
hypothetical scenario when no roadmap is available. Resolve the sibling entry
point and workflow before diagnosis; if a required file is unavailable, report
that dependency gap and retain the affected candidate as an investigation item.
Without source access, retain questions rather than claiming a diagnosis ran.

The requested result is a bounded diagnosis with inspected scope, source evidence,
heuristic references, consequential mechanisms, existing protection, alternatives,
refactoring directions, cost/risk, observable effect criteria and uncertainty. Apply
the caller's boundary explicitly: inspect implemented code and justify a direction
for human-involved `sdd-spec` discussion. Future APIs, task sequences and concrete
test or ArchUnit designs remain open. Keep this boundary in the assignment so the
shared route's transformation and acceptance questions stay at that level.
The route's common
contract/invariant/dependency questions apply regardless of the selecting metric.
Its focused rule selection replaces a full PR review for this task.

Keep one investigation per related candidate group. Follow a cold contract or
invariant owner when needed to establish the cause; record the scope expansion.
Write the bounded diagnosis to its assigned artifact. Return its identity, source
basis, inspected scope, proposed disposition and evidence references to the
orchestrator. It links that result, its gaps and rejected candidates from the
shortlist in `<report-dir>/diagnosis.md`. Further research or checks return through
the orchestrator; the architect does not launch other roles.
Inspect supplied history for mechanical changes before interpreting activity as
evidence of a maintenance problem. Metrics explain selection; they do not prove
the diagnosis or determine implementation priority.

## Assess the returned diagnosis

The group architect applies the questions below to its bounded result. The fresh
integration architect uses those diagnoses as evidence for the final recommendation
decision; revisit source for gaps or inconsistent claims rather than repeating
an adequate inspection.
Merge findings that share a cause, preserve justified non-issues and distinguish
uninspected areas from areas without findings. A rule deviation becomes a
recommendation only when the scenario, mechanism and direction of improvement are
established. Keep the heuristic
file/section with the mechanism; do not count rule matches or deviations as a
quality score. Assign readiness and separately grounded M/R/C effects here, then prioritize through
[decision output](decision-output.md). Zero justified recommendations is valid.

For each selected candidate, answer five questions with inspectable evidence:

1. What is observed? Cite the current path, declaration/signature, actual
   dependency or commit, metric record and any numerator/denominator.
2. Which representative change or behavior makes this matter? Use an upcoming
   task, a real historical change, or an explicitly hypothetical scenario grounded
   in the code. Missing a product roadmap does not block the audit.
3. How does the problem arise? Trace the knowledge crossing the boundary,
   coordinated edits, setup or error mechanism. Read both sides, affected consumers
   and wiring. For a local function read its complete body, callers and tests.
4. Which other explanation fits the same number? Check a stable shared contract,
   mechanical rewrite, generator, aggregation, rename or incomplete measurement. Identify the
   smallest accessible observation that distinguishes the consequential alternatives.
5. Is a specific action justified? Choose ready, needs_check, observe or rejected.
   Source-free metrics support hypotheses and checks, never readiness.

Keep confidence in observation, diagnosis and expected effect separate. Several
derivatives of one input are not independent confirmation. One direct source
observation can suffice; two documents are not a universal requirement.

## Compare directions against the current system

The unit of recommendation is a direction addressing one cause with enough evidence
to decide whether to develop it in `sdd-spec`. For a significant boundary change
compare the current system, the smallest useful direction and a broader option when meaningful.
For a clear local improvement, comparison with the current state suffices.
Retaining the current system is an admissible outcome.

Identify existing declarations and consumers precisely. Describe the intended
responsibility/dependency change, behavior consequences, cost drivers and signs of
achieving the effect. Leave detailed future declarations and contracts to
`sdd-spec`. Directions include:

- Move a mutable rule to its owner to remove a specific reverse dependency.
- Hide external transport/storage details behind a consumer-relevant contract;
  put translation at the integration boundary and name updated consumers.
- Split an interface by actual client needs and preserve ownership/direction.
- Extract a domain computation with explicit inputs/results from I/O orchestration.
- Consolidate verified copies of one rule under one owner.
- Correct a bypassed package contract and enforce the accepted dependency convention.

Moving files, adding interfaces, creating `common`, or mechanically lowering a
metric is not an effect by itself. Explain the concrete change scenario that becomes
more local or requires less knowledge of implementation. Check that another boundary
does not become worse. Significant unresolved trade-offs keep the effect unknown.

## Boundaries to develop in sdd-spec

For a proposed boundary, explain the responsibility, its intended owner, the
dependency direction and affected existing consumers. A sketch may expose the
current dependency and intended change without fixing a new package/API layout.
State required behavior and the property that would establish improvement.
Detailed package membership, public declarations, ArchUnit rules and import scope
are questions for subsequent design. Existing tests and architecture checks remain
evidence about the current system; inspect their coverage when a claim relies on it.

Inspect current tests for behavior and protection evidence; record remaining
validation questions in section 6. Required product behavior and explicit
performance constraints remain obligations. An actual behavior bug may
need a separately named fix. Backward compatibility, adapters and parallel APIs
are additional scope only when explicitly required.

## Stop conditions

- **ready:** an evidenced mechanism and direction, identified sources/consumers,
  required behavior and grounded effects support human-involved `sdd-spec` work.
  Implementation choices can remain open in section 6 of the card.
- **needs_check:** a consequential question, accessible next action, and how each
  possible answer changes the decision. Keep unknown effects distinct from no effect.
- **observe:** no current reason to spend the work; name a meaningful revisit trigger.
- **rejected:** explain the accepted construction or why the proposed change gives
  no useful effect; retain the reason briefly.

Ask for more data only when the answer could change the choice or its warranted
use. A large uncertainty does not automatically justify a large investigation.
If an unresolved answer could overturn the direction, retain `needs_check` and
its decision consequence. If it only chooses how to implement the direction,
record it for `sdd-spec`. Author the six sections through
[decision output](decision-output.md); do not expand the diagnosis into a design.
