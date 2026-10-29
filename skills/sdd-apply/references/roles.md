# Worker contract

Read your role instructions and generated packet. Use original REQ/AC, approved
design, project instructions and exact checks; the packet gives their paths,
owned files, prior commits, blockers and rejected approaches.
The author's conversation, grading answers and unrelated task history are not inputs.

Read documents at `HEAD` of the packet's `project_root` repository, using `sources`
to locate them. This is the main working branch, even when your task worktree has
an older HEAD. Uncommitted edits are not document inputs. The packet's task and
registered checks retain the admitted scope; return changed scope to the
orchestrator for explicit `revised_plan` reconciliation while preserving work.

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
current integrated source/plan-commit/registry basis. This scope grants verification
authority without granting implementation ownership. Report ambiguous repair
ownership before any author is reopened.

An ordinary final project verifier also has `task_id: null` when additional project
checks are registered. Its packet contains those exact additional checks, approved
covers criteria, accepted tasks and current basis. This scope supplements the
ordinary task-scoped final verifiers; it cannot replace their evidence. Every final
verifier is independent of all authors.

Return task/role/context IDs, status and commit
SHA, owned/inspected paths, AC-to-evidence mapping, commands and log
paths, blockers/limitations and actual host trace. Keep full evidence in artifacts;
the message gives the result and references. A combined verifier/reviewer context
returns distinct results for its two registered roles. Finish API work before
ending the role; DONE is an implementation claim, not acceptance.

Task verifiers submit `verification_result` for independent/integration; fresh final_verifiers submit it for final in their task or null scope before
`role_result`. Each conclusion covers the exact applicable criteria and current
basis/evidence references; role completion or explorer success cannot replace it.
See [checks and evidence](api-checks.md#criterion-conclusions) for gap requests.

The orchestrator handles launch, registration, replacement and state transitions
under [role coordination](role-coordination.md); workers need not load that procedure.

Explorer receives a bounded research or checks assignment in its role packet.
Research may have null task scope before any final registry exists. It returns
an answer, references, inspected scope, limitations, assumptions and questions
through `role_result`; the enclosing saved role supplies identity, basis and
launch evidence. Checks use `check_run` and deterministic `procedure_begin/result`.
Source files, normative documents, registries and settings remain outside the
explorer's write authority. Pass evidence references to the orchestrator.

A completed task explorer context can continue research, baseline, self,
independent and integration with a new role ID, current assignment and unchanged
launch profile. Another task and final require a separate new context. Keep every
explorer separate from executor, verifier, reviewer and final_verifier. Final has
a fresh explorer plus a separate fresh final_verifier. A completed check run or
role result does not itself establish acceptance criteria.
