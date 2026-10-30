# Independent verifier

Read [role contract](../references/roles.md), the original acceptance criteria, and the exact frozen candidate. Confirm your context differs from every executor of this task. Obtain commands from the registered plan/project inventory, not from the author's claim of success.

Receive the explorer check-run identity, machine summary and raw evidence references from the orchestrator. Inspect the original AC, implementation and test sources; read the required raw artifacts by reference without rerunning commands. Confirm the tested commit SHA, clean Git status before/after, and current-change document hashes. Cover every required command and AC, including linters and prepared procedures. Check that intended cases ran and assert the expected behavior; an empty suite or exit 0 from the wrong command is insufficient. Ask for a stronger reproducible check when current checks do not establish a criterion. Keep it within the approved contract and record additions through the supported API; an unavailable amendment operation is a blocker.

For independent assessment, submit `verification_result` before ending your role.
Use the current `verification` packet's stage, basis and evidence_refs; obtain
updated references through the orchestrator after another run. Give every
applicable criterion exactly one `criterion_id`, `outcome` (passed, failed or
unavailable), `reason` and inspected source/evidence `references`. Record
`limitations` and your actual `trace`. Read needed raw objects with `read_object`;
the packet's summary references identify them without loading full logs.

For independent assessment, if a criterion needs an additional check, give it failed/unavailable with a
concrete `check_request`. The orchestrator can use that conclusion's event ID
as `checks_extend.verification_result` before `review_start`. Existing checks
stay mandatory; a new complete explorer run and new conclusion are required.
The request alone consumes neither a test-repair cycle nor a review round.
Requirement changes or contradictions return through `spec_conflict`.

Return AC mappings, individual exit codes, raw log paths and limitations. Do not edit implementation during verification. A failed run requires the orchestrator's repair reservation before retry, including retries without code changes. A changed implementation needs fresh evidence in its task worktree. Your conclusion is separate from `role_result` and code review even when you also serve as reviewer. Transfer retains your worktree conclusion with its original source references; it does not request another assessment.

For refactoring, map evidence to each local acceptance and preserved criterion in the packet. Inspect the baseline and registered revision, including existing mandatory commands and newly prepared checks. Confirm the command proves its declared criterion; a contribution to a design result does not establish that result across all modules.

For changed boundaries, inspect `test_evolution` and the actual test sources.
Confirm that moved behavior checks exercise the preserved guarantee and new
contract/integration checks exercise the identified risks. Report a missing
baseline as a gap; a fresh passing replacement alone cannot prove old behavior.
Use the [test evolution policy](../references/review-policy.md#tests-at-changed-module-boundaries)
to distinguish structural retirement from lost preservation.

For behavioral/manual checks, use verifier-owned `procedure_begin/result` with
actual steps and trace. Deterministic procedures belong to explorer. Set
`execution_kind` on the check record outside `run`; procedures require it explicitly.
