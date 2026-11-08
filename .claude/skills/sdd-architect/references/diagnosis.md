# From a candidate to a feasible change

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

Pass the candidate's paths/declarations, revision and working state, selection
reason, qualified metric records and limitations, known change/behavior scenario,
required behavior and relevant source/history evidence. Use a source-grounded
hypothetical scenario when no roadmap is available. Resolve the sibling entry
point and workflow before diagnosis; if a required file is unavailable, report
that dependency gap and retain the affected candidate as an investigation item.
Without source access, retain questions rather than claiming a diagnosis ran.

The requested result is a bounded diagnosis with inspected scope, source evidence,
heuristic references, consequential mechanisms, existing protection, alternatives,
feasible changes, cost/risk, acceptance checks and uncertainty. The route's common
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
recommendation only when the scenario, mechanism and feasible improvement are
established. Keep the heuristic
file/section with the mechanism; do not count rule matches or deviations as a
quality score. Assign readiness and M/R/S effects here, then prioritize through
[decision output](decision-output.md). Zero justified recommendations is valid.

For each selected candidate, answer five questions with inspectable evidence:

1. What is observed? Cite the revision, full path, declaration/signature, actual
   dependency or commit, metric record and any numerator/denominator.
2. Which representative change or behavior makes this matter? Use an upcoming
   task, a real historical change, or an explicitly hypothetical scenario grounded
   in the code. Missing a product roadmap does not block the audit.
3. How does the problem arise? Trace the knowledge crossing the boundary,
   coordinated edits, setup or error mechanism. Read both sides, affected consumers
   and wiring. For a local function read its complete body, callers and tests.
4. Which other explanation fits the same number? Check a stable shared contract,
   mechanical rewrite, generator, aggregation, rename or stale report. Identify the
   smallest accessible observation that distinguishes the consequential alternatives.
5. Is a specific action justified? Choose ready, needs_check, observe or rejected.
   Source-free metrics support hypotheses and checks, never readiness.

Keep confidence in observation, diagnosis and expected effect separate. Several
derivatives of one input are not independent confirmation. One direct source
observation can suffice; two documents are not a universal requirement.

## Compare changes against the current system

The unit of recommendation is a complete change addressing one cause, including
necessary preparation tests. For a significant boundary change compare the current
system, the smallest useful transformation and a broader option when meaningful.
For a clear local improvement, comparison with the current state suffices.
Retaining the current system is an admissible outcome.

Name responsibility and contract ownership before/after, concrete declarations,
consumers, dependencies, behavior consequences, effort and acceptance. Options:

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

## Boundaries implemented through packages

For every new or changed boundary, specify:

| Decision | Required content |
| --- | --- |
| Ownership | Package membership and the module's responsibility |
| Public contract | Allowed packages/declarations and hidden implementation details |
| Dependencies | Allowed direction and consumer entry points |
| ArchUnit acceptance | Reused, changed or proposed rule; one forbidden dependency it must detect and an allowed example |
| Import scope | Compiled classes of the module **and consumers**, across all relevant build outputs |

Use project naming conventions. An `internal` package is a convention; Kotlin's
`internal` modifier restricts compilation-module visibility, not package boundaries
inside one compilation. ArchUnit checks the accepted convention. An incomplete
import scope cannot establish isolation; report missing consumers explicitly.
Apply acyclicity only where it is an accepted architecture requirement.

Check current tests before adding preparation work. Required product behavior and
explicit performance constraints remain obligations. An actual behavior bug may
need a separately named fix. Backward compatibility, adapters and parallel APIs
are additional scope only when explicitly required.

## Stop conditions

- **ready:** verified mechanism, feasible concrete transformation, identified
  sources/consumers and acceptance; known effects can be compared.
- **needs_check:** a consequential question, accessible next action, and how each
  possible answer changes the decision. Keep unknown effects distinct from no effect.
- **observe:** no current reason to spend the work; name a meaningful revisit trigger.
- **rejected:** explain the accepted construction or why the proposed change gives
  no useful effect; retain the reason briefly.

Ask for more data only when the answer could change the choice or its warranted
use. A large uncertainty does not automatically justify a large investigation.
