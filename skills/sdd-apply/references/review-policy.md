# Review findings and technical debt

Apply this policy to task, integration, and final code reviews. Accept a finding
for repair only when evidence demonstrates a violation of at least one approved
acceptance criterion, accepted architecture decision, or applicable project rule.
This keeps implementation within the agreed scope while preserving useful ideas.

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

For refactoring, read the packet's `test_evolution`: approved `test_changes`
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

Use `more_checks` for a specific unresolved contractual evidence gap. Use a
proven blocker when a preserved guarantee or accepted architecture is violated.
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
Use `more_checks` only to resolve a specific gap in evidence for an AC,
architecture decision, or project rule; explain that gap in `test_integrity`.

After completing the plan and final verification, finalize with debt deferred by
default. A nonempty journal does not prevent completion. Present a brief summary
of the debt, its consequences, and proposed fixes, with a link to the journal.
Ask which items the user explicitly approves for correction, then wait before
changing any of them. Approval of the plan, general autonomy, silence, or a
reviewer's recommendation is not approval to fix technical debt. Preserve the
completed result if the user declines or does not reply.

Record any explicit follow-up decision against the journal's finding IDs, with
the user's message source and text. Implement only the approved items as scoped
follow-up work with the applicable checks; return to sdd-spec if the work changes
the normative contract. Do not reopen the completed plan automatically.
