# Code lens

Answer: does the implementation follow the accepted architecture and applicable
code rules, and what structural problems make it harder to understand or maintain?

Own module boundaries, dependencies, interfaces, placement of responsibilities,
unnecessary complexity, duplication, naming and project rules about writing code.
Read the approved design and the complete owned implementation diff, including
configuration. Report concrete architecture or code-rule violations with proof;
other improvements are recommendations recorded as technical debt.

For an ordinary change or refactoring affecting software, explicitly read
[sdd-code-design](../../sdd-code-design/SKILL.md) and use
[focused diagnosis](../../sdd-code-design/workflows/diagnose-code.md) with
**implemented code** as the work product.
The candidate is the complete owned implementation diff at the frozen commit;
inspect affected consumers and contracts where needed. Select references from
the sources independently of the author. The diagnosis supplies evidence and
mechanisms for this lens's existing findings, within the review policy's proof,
severity and repair rules. Route behavior and test-sufficiency observations to
verification; suggested checks go to the orchestrator. Execute no diagnosis checks.

For refactoring, read the accepted target, original behavior sources, local
acceptance, `contributes_to`, `preserves` and test-change decisions. Assess the
task's structural contribution and consumer obligations at the current transition
stage; whole-result criteria may become due in later tasks. Keep preservation and
test-sufficiency judgments with verification, including gaps in the original
baseline and behavioral assertions affected by structural test removal.

Use these questions where the changed code exposes the relevant concern:

- **Invariants:** where are domain constraints enforced across parsing,
  construction and mutation? Are there paths around that boundary or scattered
  copies of the same validation rule?
- **Responsibilities:** does a unit combine unrelated responsibilities, side
  effects or abstraction levels? Do its data and dependencies belong together,
  or does it mostly manipulate another module's internals?
- **Interfaces:** do names, types and operations make valid use and side effects
  clear? Does the interface permit invalid combinations or require callers to
  know a hidden ordering of operations?
- **System complexity:** does a local simplification introduce dependency cycles,
  layer violations, duplicated rules or broader coupling elsewhere? Does a new
  abstraction or dependency duplicate an existing capability?

The verification lens owns REQ/AC compliance, observable behavior, assertions,
test coverage, test weakening and command/log sufficiency. Do not repeat those
assessments or supply `test_integrity`, `verification_result` or `more_checks`.
Code findings use an empty `criteria` list and cannot use `proof.kind: acceptance`.
If a finding concerns a test file, assess only its code structure; its assertions
and preserved guarantees remain the verification lens's responsibility.

For a mixed concern, separate the properties: the code lens assesses the dependency
or boundary; verification assesses the required behavior and evidence. Send facts
outside your scope to the orchestrator, naming the verification lens, without
turning them into duplicate findings. Do not read the other reviewer's conclusions.

Return `review_result` with architecture/code findings and actual trace. Use `changes`
only for proven violations of the accepted design or applicable code rules;
recommendations alone permit `pass`. Execute no checks or procedures.
