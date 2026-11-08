# Refactor Code Workflow

Design or implement a structural change within a declared boundary of preserved
behavior. Use this workflow for refactoring code, interfaces or test boundaries.
For an assessment of a proposal or completed code, use
[focused diagnosis](diagnose-code.md) in the caller's review lens.

## Choose the Work Product

Use **proposed design** to compare structures and describe a transformation before
implementation. Use **implementation** for an authorized task with an accepted
target and preservation obligations. The caller governs scope, decisions, write
permissions, baseline collection, check execution, commits and acceptance.

Identify the structural result, affected consumers, preserved observable behavior
and constraints. Distinguish internal interfaces that may change together with
their consumers from contracts that must remain stable. Compatibility adapters,
old formats and parallel paths require explicit scope authorization; a generic
refactoring heuristic does not add them.

Return a conflict that would change required behavior or the accepted architecture
to the caller before dependent work. Preserve the supported independent result.

## Proposed Design

1. **Establish the current construction and evidence.** Read the affected code,
   consumers, contracts and tests. Reuse an applicable diagnosis or research result,
   checking its sources and scope. Separate observed behavior from assumptions and
   missing evidence. When preservation lacks adequate evidence, propose a
   characterization check on the original implementation before transformation.
   A check run only on transformed code cannot establish the original behavior.
2. **Explain the structural gain.** Trace a concrete maintenance or change scenario
   through the current construction. Label a hypothetical scenario as such.
   Compare retaining the construction, the smallest useful change and any materially
   different alternative. Show which responsibility, implementation knowledge or
   repeated work changes for owners and consumers, including new burdens and risks.
   Fewer helpers, files or lines alone do not establish an improvement.
3. **Design the target and transition.** Describe responsibility and invariant owners,
   dependencies and effect ordering. Identify usable intermediate states and the
   consumers each affects. Select one primary reference and at most two secondary
   references from [the refactoring guide](../guidelines.md#refactoring):

   - For interface changes, compare [consumer obligations](../references/decomposition/rules.md#11-compare-consumer-obligations-before-and-after).
   - For suspected redundant abstractions, apply [hypothetical removal](../references/decomposition/rules.md#12-mentally-remove-a-suspected-indirection).
   - For policy mixed with representation, compare [semantic layers](../references/decomposition/stratified-design.md).
   - When moving reads, writes or resource boundaries, apply [effect preservation](../references/decomposition/patterns.md#preserve-behavior-when-moving-effects).
4. **Define discriminating checks.** Separate checks of the target structure from
   checks of preserved behavior. For each affected test group, identify its old
   guarantee and proposed disposition. A purely structural check for an explicitly
   retired boundary may disappear; a mixed test retains its behavioral assertions
   at a suitable boundary. Propose contract and interaction cases for new boundaries
   according to the concrete risk. Use the caller's test-evolution and check-registry
   rules to authorize and record changes.

Return the current and target construction, comparison, preservation sources and
gaps, transition and proposed checks in the caller's existing documents. In SDD,
map structural outcomes to `result`, preserved guarantees to `preservation` with
their sources, and significant choices to DEC linked through `criteria`. Carry
accepted choices into `contributes_to`, `preserves`, `test_changes` and whole-result
CHECKs when the caller authorizes planning. The refactoring route uses proposal,
design and tasks; it does not require new specs or invented REQ identifiers.

Stop at the design result. Characterization and other checks here are proposals;
their execution belongs to an authorized implementation or evidence assignment.

## Implementation

1. **Read the accepted task and baseline.** Recover the target, owned paths, local
   acceptance, applicable preservation obligations, approved test changes and
   relevant decisions. Follow the caller's baseline readiness rule before editing
   production code. Obtain any assigned missing characterization evidence on the
   original implementation first. An unresolved evidence gap stays explicit and
   blocks only work that relies on the unsupported guarantee.
2. **Transform within the task.** Use the accepted design to choose local boundaries
   and references; keep architectural reconsideration with the caller. Preserve
   required input consumption, failure handling, transaction boundaries and resource
   lifetimes when extracting calculations or moving effects. Maintain a usable
   intermediate result. A task's contribution to the target is distinct from
   completion of the whole refactoring.
3. **Evolve tests with their guarantees.** Apply the approved dispositions to actual
   assertions and files. Retain the behavioral part of mixed tests and identify
   replacement checks where required. Follow the caller's independent confirmation
   of registry revisions before retiring registered checks. Characterization tests
   need no artificial red phase; their evidence comes from the original behavior.
4. **Verify and return evidence.** Run only checks permitted or assigned by the
   caller, including local self-checks. Report the changed construction, coverage of
   local acceptance and preservation, test changes, performed checks and remaining
   gaps. Distinguish available whole-result evidence from checks planned for later
   tasks. The caller's independent verification and review determine acceptance.

For example, a streaming publisher may extract its decision into a pure function
while retaining read-compute-publish ordering in the shell. Materializing all input
first would consume later records even when publication fails. A failure case that
checks no subsequent record was read tests the preserved contract; a separate check
establishes the selected calculation boundary.
