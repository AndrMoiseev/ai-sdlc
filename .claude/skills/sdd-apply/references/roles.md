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
Reviewers apply only their assigned lens to this context. The verification lens assesses
local acceptance and preservation; code assesses architecture and code rules.
Contributions describe intended scope, not whole-result success. Use the current
frozen commit and registry; transfer retains the task reviews.

The refactoring packet's `test_evolution` carries approved groups, complete
applicable check records, the pending transition including its actual-test mapping,
and the confirmed revision. These are facts, not instructions to assess another
role's responsibility. The executor uses them to prepare test changes; the
verification reviewer uses them to assess coverage under the
[boundary-test policy](review-policy.md#tests-at-changed-module-boundaries).

Work only within the assignment. Reviewers are independent of all authors and
other reviewers and do not edit the candidate or execute checks. Wait for the
generated packet and your lens's successful `review_start`. Report unavailable inputs,
permissions or tools rather than simulating a role or a successful check.

The verification reviewer submits `verification_result` before its `review_result`.
Each conclusion covers the exact applicable criteria and current basis/evidence
references; role completion or Explorer success cannot replace it. Code reviewers
do not submit criterion conclusions or test-integrity assessments.
See [checks and evidence](api-checks.md#criterion-conclusions) for gap requests.

The orchestrator handles launch, registration, replacement and state transitions
under [role coordination](role-coordination.md); workers need not load that procedure.

Explorer receives a bounded research or checks assignment in its role packet.
Research may have null task scope without a check registry. It returns
an answer, references, inspected scope, limitations, assumptions and questions
through `role_result`; the enclosing saved role supplies identity, basis and
launch evidence. Checks use `check_run` and deterministic `procedure_begin/result`.
Source files, normative documents, registries and settings remain outside the
explorer's write authority. For checks, execute only the orchestrator's complete
assignment and report actual outcomes; make no selection, acceptance or repair
decisions. Pass evidence references to the orchestrator.

A completed task explorer context can continue research, baseline, self,
or independent checks with a new role ID, current assignment and unchanged
launch profile. Another task requires a separate new context. Keep every
explorer separate from executor and every reviewer. A completed check run or
role result does not itself establish acceptance criteria.
