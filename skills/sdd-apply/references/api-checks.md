# Checks, candidates and evidence

Read before registering or running checks, freezing a candidate, or assessing
evidence. Use installed event help for exact fields.

## Check registry

For work on skills, apply the [skill development acceptance rule](../SKILL.md#skill-development-acceptance)
before registering checks: task stages use deterministic tests, and behavioral
checks run only at final acceptance of the whole plan.

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
Candidate and command evidence bind the current registry revision. Removing or
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

Later tasks and task-scoped `final` checks use the confirmed applicable set.
Retired adapter checks remain historical observations with their original
outcomes. Inspect `resume.check_registries` for the confirmed revision/checks and
the separate pending transition after an interruption. Resume preserves that
split and existing authorization; it cannot finish a revision from task status
or an orphaned log. Exact event replay returns the saved result. Different
content requires a new event/revision and fresh checks and review.

For verification/review of a transition, read the saved registry object and its
history and `transition` alongside the role packet, resolving `read_object`
references as needed. Existing compact packets show
registry hashes rather than the complete pending mapping. Carry the actual
confirmed/pending fields and selected checks as supplemental role material.

Every command is an argument array passed unchanged with `shell=False`. Register
a required interpreter explicitly. Legacy strings are rejected at registration;
persisted strings produce `unavailable` with `limitation: command_format`.
Preserve their evidence and revise the incompatible plan. Changing command
representation invalidates registry/candidate evidence and needs fresh checks.

## Running checks

`check_run` executes the complete applicable registry for the assigned `role_id` and stage
(`baseline`, `self`, `independent`, `integration`, `final`), with optional timeout.
For a registered procedure, use `procedure_begin` with check/role/stage, execute
it in that role, and submit `procedure_result` with the same IDs, outcome, actual
steps and host trace. Then `check_run` reconciles the full assigned set. Git commit
identity and a clean working copy detect drift; a procedure's semantic result is
a role attestation, not an exit code. Stop writers for the entire check. Ignored
files may hold generated output or disposable environments; test inputs and
source code must be tracked.

After `more_checks`, `checks_extend` takes the requesting `review_round` and
additional checks. Existing checks stay mandatory; new registry contents
invalidate prior verification. Apply [repair](../flows/repair.md) before fixes
or retries after failure.

## Candidate identity

`candidate` commits the stopped executor's owned changes on the local task
branch. After integration, the same event commits the integrated result before
integration checks. A commit records a candidate; acceptance still requires the
current checks and review. Reuse the identical event after an interrupted commit
so its durable intent can recover the result.

Candidates are compact references with `candidate_id`, `sha256`, `path` and checked
`root`. The payload under `candidates/` records the tested Git commit, current-change
documents, normative manifest and check registry. Its `sha256` identifies that
canonical JSON payload. Pass the returned reference unchanged. The script checks
the same commit and clean tracked/index/untracked state before and after tests
and before reusing evidence. A status list alone cannot identify a dirty candidate.

File-content snapshots are limited to the current change/refactoring directory,
excluding `execution/`. Do not enumerate and hash repository sources, installed
skill copies or unrelated documents. Git already records committed source content.
Keep old source-snapshot evidence as history; it cannot certify a new commit
candidate. Resume requires a fresh candidate and checks under this contract.

## Evidence gates

Retain command, stdout/stderr, exit status, duration, tested commit SHA, Git
cleanliness observations, current-change document hashes, launch
trace and log hash. Inspect whether expected tests ran; a later successful
command cannot repair an earlier failure. Unknown dependency scope needs rechecking.
Changed bytes, configuration, registry or normative basis invalidate affected
evidence. A required unavailable check blocks; omission cannot make it green.

Final checks use fresh `final_verifier` roles and a clean final-HEAD candidate separate
from historical task candidates. Earlier logs do not replace that final run.
