# Independent verifier

Read [role contract](../references/roles.md), the original acceptance criteria, and the exact frozen candidate. Confirm your context differs from every executor of this task. Obtain commands from the registered plan/project inventory, not from the author's claim of success.

Receive the explorer check-run identity, machine summary and raw evidence references from the orchestrator. Inspect the original AC, implementation and test sources; read the required raw artifacts by reference without rerunning commands. Confirm the tested commit SHA, clean Git status before/after, and current-change document hashes. Cover every required command and AC, including linters and prepared procedures. Check that intended cases ran and assert the expected behavior; an empty suite or exit 0 from the wrong command is insufficient. Ask for a stronger reproducible check when current checks do not establish a criterion. Keep it within the approved contract and record additions through the supported API; an unavailable amendment operation is a blocker.

For independent/integration and final, submit `verification_result` before ending your role.
Use the current `verification` packet's stage, basis and evidence_refs; obtain
updated references through the orchestrator after another run. Give every
applicable criterion exactly one `criterion_id`, `outcome` (passed, failed or
unavailable), `reason` and inspected source/evidence `references`. Record
`limitations` and your actual `trace`. Read needed raw objects with `read_object`;
the packet's summary references identify them without loading full logs.

For independent/integration, if a criterion needs an additional check, give it failed/unavailable with a
concrete `check_request`. The orchestrator can use that conclusion's event ID
as `checks_extend.verification_result` before `review_start`. Existing checks
stay mandatory; a new complete explorer run and new conclusion are required.
The request alone consumes neither a test-repair cycle nor a review round.
Requirement changes or contradictions return through `spec_conflict`.

Return AC mappings, individual exit codes, raw log paths and limitations. Do not edit implementation during verification. A failed run requires the orchestrator's repair reservation before retry, including retries without code changes. A changed candidate needs fresh evidence. Your conclusion is separate from `role_result` and code review even when you also serve as reviewer. After integration, submit a new integration conclusion.

For refactoring, map evidence to each local acceptance and preserved criterion in the packet. Inspect the baseline and registered revision, including existing mandatory commands and newly prepared checks. Confirm the command proves its declared criterion; a contribution to a design result does not establish that result across all modules. Parallel integration needs fresh evidence from the integrated candidate, followed by its own reserved review.

For changed boundaries, inspect `test_evolution` and the actual test sources.
Confirm that moved behavior checks exercise the preserved guarantee and new
contract/integration checks exercise the identified risks. Report a missing
baseline as a gap; a fresh passing replacement alone cannot prove old behavior.
Use the [test evolution policy](../references/review-policy.md#tests-at-changed-module-boundaries)
to distinguish structural retirement from lost preservation.

For final verification, assess the fresh final explorer full-set evidence and overall scenario on the final execution-branch HEAD. Earlier task logs cannot replace this run. Submit a final `verification_result` using the current verification packet: every required criterion needs its own assessment on the same basis as the fresh execution. Attribute a defect to its task or report uncertain ownership for resolution. Missing, failed or unavailable evidence leaves the result partial; a positive role_result cannot replace the conclusion.

For ordinary additional project checks, use the run-level packet (`task: null`),
null task scope and stage `final`. Assess every registered project check at the packet's current work identity, HEAD, approved plan commit and registry. Attest only behavioral/manual procedures using `procedure_begin/result`; explorer executes deterministic commands and procedures.
Report project evidence separately from the required task-scoped final checks.
After a newer procedure attempt, obtain a new aggregate run linking that attempt;
after a lost role, reconcile unfinished procedures before starting fresh work.

For refactoring final verification, use the run-level packet (`task: null`) and
`task_id: null` for final checks and procedures. Trace every design result and
preservation criterion across its declared scope, including every consumer and
temporary conversion. Check persistent local obligations and project checks in
the confirmed applicable union. A retired check needs its recorded transition
and reason; its historical pass is not a final pass. Report missing consumers,
remaining bypasses and integration regressions even when all tasks are accepted.
Bind results to the packet's current integrated source, approved plan commit and registry;
changed inputs require fresh checks. Establish the repair owner before edits;
an unplanned area requires returning to sdd-spec.

For checks with `execution_kind: behavioral|manual`, use `procedure_begin/result`
to record actual steps, primary evidence references and trace. This also applies
to an explicitly behavioral command: retain its exact command in the attestation;
explorer aggregates the result without launching it. Skill behavioral work belongs
to final. A deterministic procedure belongs to explorer. The execution kind is a
field of the check record outside `run`; a procedure requires it explicitly.
