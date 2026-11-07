# From a candidate to a feasible change

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
