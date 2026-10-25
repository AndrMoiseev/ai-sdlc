# Worker contract

Read your role instructions and generated packet. Use original REQ/AC, approved
design, project instructions and exact checks; the packet gives their paths,
owned files, candidate reference, prior commits, blockers and rejected approaches.
The author's conversation, grading answers and unrelated task history are not inputs.

For refactoring, the packet's `refactoring` context contains scope, original local
acceptance records, preserves, contributes_to, test_changes, relevant design
criteria/decisions, original document paths, registry history and baseline.
Verify local acceptance and preservation independently. Contributions describe
intended scope; they do not establish whole-result success. Use the current
candidate and registry for task review and subsequent integrated-state review.

The refactoring packet's `test_evolution` carries approved groups, complete
applicable check records, the pending transition including its actual-test mapping,
and the confirmed revision. Treat this as review input, not a coverage verdict.
Read the [boundary-test policy](review-policy.md#tests-at-changed-module-boundaries)
when tests change with module boundaries.

Work only within the assignment. Verifiers and reviewers are independent of all
authors and do not edit the candidate. Wait for the generated packet; a reviewer
also waits for a successful `review_start` reservation. Report unavailable inputs,
permissions or tools rather than simulating a role or a successful check.

A refactoring final verifier has `task_id: null`. Its run-level packet contains
the whole criteria, original document paths, accepted task scopes and commits,
the confirmed applicable check union, retired checks with reasons, and the
current integrated source/manifest/registry basis. This scope grants verification
authority without granting implementation ownership. Report ambiguous repair
ownership before any author is reopened.

Return task/role/context IDs, status, unchanged candidate reference and commit
SHA, owned/inspected paths, AC-to-evidence mapping, commands and log
paths, blockers/limitations and actual host trace. Keep full evidence in artifacts;
the message gives the result and references. A combined verifier/reviewer context
returns distinct results for its two registered roles. Finish API work before
ending the role; DONE is an implementation claim, not acceptance.

The orchestrator handles launch, registration, replacement and state transitions
under [role coordination](role-coordination.md); workers need not load that procedure.
