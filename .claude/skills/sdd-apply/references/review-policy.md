# Review findings and technical debt

## Review lenses

After the full project tests and static checks pass, run both required lenses in
parallel against the same frozen commit. Each reviewer has one `lens_id` and a
separate fresh context. A round completes only with both results; every
lens must pass before integration. Reviewers execute no checks or procedures.

Reuse applicable results when their basis is unchanged. After a verification
`more_checks` result, evidence-only additions require a fresh verification lens
in the next round; retain a passing code verdict by reference to its original
round. This is valid only while the source, approved task and owned paths remain
unchanged. New code, tests, configuration, dependencies, resolved conflicts or a
revised task contract require both lenses again. Preserve the original reviewer,
commit and trace when reusing a verdict; never present it as a new review. An
unchanged passing result needs neither another round nor another check run.

| Lens | Exclusive responsibility | Result |
| --- | --- | --- |
| [verification](verification-lens.md) | REQ/AC compliance, observable behavior, test sufficiency and integrity, evidence freshness, project testing rules | `verification_result` and `review_result` with `test_integrity`; may request `more_checks` |
| [code](code-lens.md) | Accepted architecture, source structure, dependencies, maintainability and project code rules | `review_result`; no criterion verdicts, test-integrity assessment or check execution |

Assign a question by the property being assessed, not by filename. A test's
assertion strength belongs to verification; its source structure belongs to code.
For project rules, testing/evidence rules belong to verification and implementation
rules to code. Send out-of-scope observations to the orchestrator, naming the owning
lens. Do not duplicate findings or read another lens's report during independent work.

## Finding policy

Apply this policy to task code reviews. Accept a finding
for repair only when evidence demonstrates a violation of at least one approved
acceptance criterion, accepted architecture decision, or applicable project rule.
This keeps implementation within the agreed scope while preserving useful ideas.

When another design skill is explicitly active, use its heuristics within this
policy's review roles, check-execution limits, verdicts and repair scope. Treat
heuristics as questions for investigation; a heuristic alone is not an applicable
project rule or proof of a violation.

For each finding, identify the affected code and observable behavior. For a
contractual defect, include `proof: {kind, source, violation}`:

- `kind`: `acceptance`, `architecture`, or `project_rule`.
- `source`: the original document path plus criterion/decision/rule ID or section.
- `violation`: concrete code, test, or log evidence explaining how the candidate
  contradicts that source. A source citation alone is insufficient.

Verify that the cited source is accepted and applicable; never invent a rule to
justify a preferred change. The script checks the proof's structure; the reviewer
and orchestrator remain responsible for its truth and applicability.

Classify proven violations as `blocker`. Classify every other finding as
`recommendation` and retain it in the technical debt journal. Severity labels,
generic best practices, an easy fix, or reviewer insistence do not replace proof.
Unexplained test weakening is a blocker only with evidence of an affected AC or
project rule. Keep mandatory checks and their failure handling unchanged.

## Tests at changed module boundaries

In the verification lens, read the packet's `test_evolution`: approved `test_changes`
groups, applicable checks, and the exact pending registry transition. Match each
actual test addition, adaptation, move or removal to its group and criteria;
identify the accepted DEC for a cancelled structural restriction. Inspect the
test diff and original baseline rather than treating the author's mapping as proof.

Distinguish the guarantees inside each test. A test solely for a cancelled
internal call may disappear without recreating that call elsewhere. A mixed
test that also checks atomicity, error handling or another preserved behavior
keeps those assertions at an appropriate public or integration boundary. Moving
a persistent property's test retains the criterion ID and its lifetime.

For a new boundary, assess contract inputs, outputs, errors and interactions
against the approved design and failure risks. The executor chooses concrete
files and cases within the assigned scope and approved groups. Test count,
coverage percentage and a green run do not establish this sufficiency. Record
the old guarantee, its disposition, actual replacement tests where needed,
registry IDs and remaining evidence gaps in `test_integrity`.

Use `more_checks` for a specific unresolved evidence gap in this lens. Use a
proven blocker when a preserved guarantee or testing rule is violated. Architectural
violations belong to the code lens.
Do not block a justified structural retirement merely because a test was deleted.
Changing the preservation obligation or architecture requires `spec_conflict`,
not a weaker oracle. Apply registry changes through `checks_revise`; state edits
and review prose cannot confirm a revision.

## Recording the review

Submit all findings through `review_result`. The script normalizes their severity
using the proof and generates `execution/technical-debt.md` from recorded reviews.
If only recommendations remain and mandatory verification is sufficient, return
`pass`: continue the plan without editing code for those recommendations, asking
for approval mid-plan, or starting another repair/review cycle solely for them.
Only verification uses `more_checks`, for a specific gap in criterion or test
evidence; explain that gap in `test_integrity`. Code findings concern accepted
architecture and implementation rules and use `pass` or `changes`.

After accepting all plan tasks, finalize with debt deferred by
default. A nonempty journal does not prevent completion. Present a brief summary
of the debt, its consequences, and proposed fixes, with a link to the journal.
Report that the recommendations are available; do not add a mandatory follow-up
question. Fix them only after an explicit user request. Approval of the plan,
general autonomy, silence, or a reviewer's recommendation is not such a request.
Preserve the completed result when no correction is requested.

Record any explicit follow-up decision against the journal's finding IDs, with
the user's message source and text. Implement only the approved items as scoped
follow-up work with the applicable checks; return to sdd-spec if the work changes
the normative contract. Do not reopen the completed plan automatically.
