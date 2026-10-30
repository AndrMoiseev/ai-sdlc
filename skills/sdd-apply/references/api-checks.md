# Checks, candidates and evidence

Read before registering or running checks, freezing a candidate, or assessing
evidence. Use installed event help for exact fields.

## Check registry

For work on skills, apply the [skill development acceptance rule](../SKILL.md#skill-development-acceptance)
before registering checks: task stages use deterministic tests, and behavioral
checks require explicit authorization and a task or separate evaluation request.

Read the installed sdd-shared `references/document-format-tasks.md`, section
«Задача и ее проверка». `location` is relative to project or active worktree,
independent of command cwd. At `check_run` it must identify an existing file or
directory for every run variant; otherwise the check is `unavailable`, even if
the command exits 0 or a procedure reports success. Additional checks may omit
location; when supplied, the same rule applies. Existence alone does not prove
the expected tests ran.

Register exact commands, cwd, configuration, source and AC before implementation,
including project instructions and CI. `checks_register` takes inspected
`inventory: {instructions: [...], ci: [...]}` and `additional` checks; explicit
empty inventories are valid. An absent applicable linter is an explained inventory
fact, not a successful check. Keep existing mandatory checks.

Only unresolved `setup_required` is `planned_absence` at baseline. It permits
creating an approved future test or preparing its runner in that task. After
baseline capture, `check_setup` resolves the planned command/procedure with its
exact command, description and optional cwd/configuration. Record before/after
setup, run existing checks independently, and preserve assertion strength.
Missing location under command/procedure blocks; return a wrongly planned future
check to sdd-spec instead of changing the approved run.

Refactoring checks use the stable key `TASK-ID/verification.id`. Their criteria
are local acceptance records owned by that task or its `preserves` criteria;
`contributes_to` is separate. Registration, prepared setup and review-requested
extensions append immutable registry snapshots. Baseline logs retain exact
initial checks and their revision, including existing preservation commands.
Command evidence records the current registry revision. Removing or
rewriting a check directly blocks freezing and acceptance; an authorized registry
transition requires a supported operation and independent confirmation. Keep
historical logs.

In refactoring work, registration and review-requested extension cannot reuse
another task's check ID. This includes additional project checks, retired IDs,
and generated keys reserved by the approved plan before registration. Use an
authorized `checks_revise` transition to change an existing obligation. Ordinary
change work retains task-local check IDs.

### Approved refactoring revisions

Use `checks_revise` after baseline, within the running task or its reserved repair.
Read its installed event help for the complete record shape. Submit the current
`registry_revision`, exact applicable `before` and complete `after` records,
approved `basis`, affected `preserves`, `reason`, and a `mapping` for every changed
check. The mapping identifies the approved test group or transitional criterion
and the actual tests affected. Keep unchanged project and CI checks in `after`.

Bind `basis.test_changes` to this task's approved local change IDs. Bind
`basis.transitional_criteria` to acceptance criteria whose `until_task` is this
task. The replacing state needs executable checks at task acceptance; final-only
evidence cannot retire an adapter check. A moved preservation test keeps its
criterion ID. A structural retirement uses its approved architecture decision.
Changing the obligation, group or lifetime itself returns through
`spec_conflict` and `revised_plan`.

The script stages a revision and retains the original registry snapshots and logs.
Its pending applicability lets the removal candidate run the replacing-state
checks after the old boundary is gone. Freeze a new candidate, run independent
checks and review, and confirm the task commit. `accept` confirms the new
applicability in the same state write as task acceptance. Failed or unavailable
replacement checks keep the task unaccepted; reserve repair before editing or
retrying and retain the existing lifetime counters.

Later tasks use the confirmed applicable set.
Retired adapter checks remain historical observations with their original
outcomes. Inspect `resume.check_registries` for the confirmed revision/checks and
the separate pending transition after an interruption. Resume preserves that
split and existing authorization; it cannot finish a revision from task status
or an orphaned log. Exact event replay returns the saved result. Different
content requires a new event/revision and fresh checks and review.

For verification/review of a transition, read `refactoring.test_evolution` in
the role packet: it includes the approved groups, selected checks, exact pending
transition and confirmed revision. Resolve the saved registry history through
`read_object` when earlier evidence is needed. Inspect actual test sources against
the mapping under the [boundary-test policy](review-policy.md#tests-at-changed-module-boundaries).

Every command is an argument array passed unchanged with `shell=False`. Register
a required interpreter explicitly. Legacy strings are rejected at registration;
persisted strings produce `unavailable` with `limitation: command_format`.
Preserve their evidence and revise the incompatible plan. Changing command
representation needs fresh checks against the updated registry.

## Running checks

`check_run` executes the complete applicable registry for the assigned `role_id` and stage
(`baseline`, `self`, `independent`), with optional timeout. The API also
retains the legacy `integration` stage; ordinary transfer does not dispatch it.
For a registered procedure, use `procedure_begin` with check/role/stage, execute
it in that role, and submit `procedure_result` with the same IDs, outcome, actual
steps and host trace. Then `check_run` reconciles the full assigned set. Git commit
identity and a clean working copy detect drift; a procedure's semantic result is
a role attestation, not an exit code. Stop writers for the entire check. Ignored
files may hold generated output or disposable environments; test inputs and
source code must be tracked.

`checks_extend` accepts exactly one basis: the current verifier conclusion's
event ID in `verification_result`, or the requesting reviewer `more_checks`
`review_round`. The verifier path works before `review_start`; see
[criterion conclusions](#criterion-conclusions). Existing checks stay mandatory;
registration, setup and extension advance the registry revision. New registry
contents invalidate prior execution and conclusions. Apply
[repair](../flows/repair.md) before fixes or retries after failure.

## Candidate identity

`candidate` is the existing event name for committing the stopped executor's
owned changes and entering verification. After integration, the same event
commits the recorded integration tree and enters `committing`. It returns `commit`
metadata and records the recoverable Git operation in `candidate_commit`.
Reuse the identical event after an interrupted commit so its durable intent
can recover the result.

No task candidate, candidate reference or `candidates/` artifact is recorded.
Checks and reviews do not compare a saved candidate with the current tree.
The orchestrator must run checks and review again after implementation changes
or repairs in the task worktree. Transfer retains that evidence, verifier
conclusion and review. Integration acceptance validates the recorded merge tree,
unchanged source and evidence artifacts without running checks again. Keep
writers stopped throughout checking and review.

Command logs retain before/after Git and current-change document snapshots.
Changes during a command make that run stale. Snapshot hashing remains limited
to the current SDD directory, excluding `execution/`; source files are identified
by Git rather than a repository-wide file inventory.

## Evidence gates

### Criterion conclusions

For independent/integration, the active independent task verifier submits
`verification_result` with `role_id`, `stage`, current `basis`, exact
`evidence_refs`, `criteria_results`, `limitations` and `trace`. Each criterion
appears exactly once as `criterion_id`, `outcome: passed|failed|unavailable`,
`reason` and nonempty inspected source/evidence `references`. Use the role
packet's `verification` fields, refreshed through the orchestrator after each run.
Evidence references contain check ID, check-run event ID, log path/hash and
summary object reference. Stored bytes, nested raw references and identity are
validated; matching metadata alone is insufficient.

A failed/unavailable criterion may include a concrete `check_request` describing
the missing assertion. Reference that current conclusion in `checks_extend` and
bind each exact command or explicitly typed procedure to the requested criteria.
The request and extension preserve review/test-repair counters. If preparation
needs source edits, reopen the executor through `repair` with the recorded gap
as `defect_evidence`; set `test_failure` only for an actual failed test. Run the
whole expanded registry and obtain a new conclusion. Changing requirements
requires `spec_conflict`; insufficient tests within an approved AC do not.

`review_start` and `transfer` require both a successful mandatory worktree run
and its latest passed conclusion. `commit` and `accept` validate that retained
worktree evidence and the recorded integration tree.
Source, normative basis, registry, configuration or a newer applicable attempt
invalidates the conclusion. Negative conclusions remain in history; neither an
older pass, `role_result`, self evidence nor reviewer verdict replaces them.
After transfer, keep the original source references; do not create an integration
run or conclusion. The `integration` stage remains readable for saved executions.

### Primary execution evidence

Retain command, stdout/stderr, exit status, duration, tested commit SHA, Git
cleanliness observations, current-change document hashes, launch
trace and log hash. Inspect whether expected tests ran; a later successful
command cannot repair an earlier failure. Unknown dependency scope needs rechecking.
Repeat affected checks after changes to bytes, configuration, registry or normative
basis. The orchestrator enforces this ordering; task evidence has no saved candidate
comparison. A required unavailable check blocks; omission cannot make it green.

## Plan completion

`finalize` uses accepted task records without a new run, registry or conclusion.
Keep original worktree identities in the report. Refactoring whole-result criteria
without task evidence are reported as unassessed; completion does not assert them.

## Execution ownership and one batch deadline

Only a registered explorer checks assignment for the exact stage, scope, current
basis, full check IDs and registry revision can call `check_run`. Baseline runs
before edits; self, independent and integration require stopped authors and a
frozen commit; integration requires the integrated commit. A checks assignment belongs to one task and its applicable registry. Self evidence
never replaces independent evidence.

Set `execution_kind` on the verification/check record, outside `run`.
Commands default to `deterministic`; procedures require an explicit
`deterministic`, `behavioral` or `manual`. The filename never selects a type.
Deterministic procedures use explorer `procedure_begin/result`. Behavioral/manual
procedures, including explicitly typed commands, use the task verifier. Their actual steps, exact command where present, raw
references and trace form the primary attestation. Explorer aggregates that
attestation and does not launch the semantic command. A newer or pending procedure
invalidates an older aggregate. Before retrying a failed procedure, reserve repair;
if it has not yet been aggregated, supply its defect evidence and `test_failure: true`. Semantic checks cannot be converted to a
command with `check_setup`. Behavioral checks of assigned skill packages run
only when explicitly authorized; execute them in their assigned task.

`timeout` is a positive finite budget for the entire assigned attempt, starting at
the first deterministic `procedure_begin` or `check_run`, including procedure
elapsed time, command setup and report capture. Deterministic `procedure_begin`
returns `remaining_timeout` and `check_deadline`; the host must stop its work
within that allowance. An expired begin is rejected. An over-budget result keeps
actual steps and `reported_outcome` but records unavailable with `check_deadline`
in the raw evidence. A later aggregate or replacement explorer continues the
same deadline for that source, registry, stage and repair generation. Each command
receives only the remaining budget. `assignment.limits.timeout` may cap it;
`assignment.limits.deadline`, when explicitly supplied, is an absolute ISO-8601
timezone-aware deadline that also caps it. Expiry retains completed evidence,
marks unstarted checks unavailable and blocks further work through the existing
failure path. Event replay returns the saved result without another process.
Changing explorer does not bypass failed-run repair reservations or reset lifetime
counters; a genuinely new authorized repair retry may execute a new full batch.

## Reading compact evidence

Start with the machine summary and original criteria/test sources. Check the
requested, completed and missing IDs, current basis, `source_unchanged`,
`evidence_complete` and `test_counts`, including skipped/xfailed/xpassed and
`unknown_fields`. An ordinary success need not load the full log. Open the relevant
raw object with `read_object` when a failure, skip or coverage question needs it;
retain its digest and location in the criterion assessment. Excerpts may be
truncated; the full primary artifact remains authoritative. Unknown counts are
null, not zero. Explorer diagnosis is separate from machine outcomes. Missing or
invalid required evidence, or a skipped mandatory area without other sufficient
current evidence, blocks acceptance. Reading the full log does not justify a new
execution; request an actual rerun through the orchestrator when its basis or
coverage requires one.
