# Checks, candidates and evidence

Read before registering or running checks, freezing a candidate, or assessing
evidence. Use installed event help for exact fields.

## Check registry

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

Every command is an argument array passed unchanged with `shell=False`. Register
a required interpreter explicitly. Legacy strings are rejected at registration;
persisted strings produce `unavailable` with `limitation: command_format`.
Preserve their evidence and revise the incompatible plan. Changing command
representation invalidates registry/candidate evidence and needs fresh checks.

## Running checks

`check_run` executes the complete registry for the assigned `role_id` and stage
(`baseline`, `self`, `independent`, `integration`, `final`), with optional timeout.
For a registered procedure, use `procedure_begin` with check/role/stage, execute
it in that role, and submit `procedure_result` with the same IDs, outcome, actual
steps and host trace. Then `check_run` reconciles the full assigned set. Snapshots
detect edits; a procedure's semantic result is a role attestation, not an exit code.

After `more_checks`, `checks_extend` takes the requesting `review_round` and
additional checks. Existing checks stay mandatory; new registry contents
invalidate prior verification. Apply [repair](../flows/repair.md) before fixes
or retries after failure.

## Candidate identity

`candidate` freezes the stopped executor's result. New candidates are compact
references with `candidate_id`, `sha256`, `path` and checked `root`. The full
snapshot is stored under `candidates/` relative to the execution directory.
Its `sha256` identifies the canonical JSON payload, not formatted file bytes.
Pass the returned reference unchanged; never reconstruct it from a worker's
description. The script verifies artifact integrity and source/registry/basis
freshness. Legacy inline candidates remain readable. Packets provide task paths
and original-source references; open the full snapshot only when needed.

## Evidence gates

Retain command, stdout/stderr, exit status, duration, source snapshots, launch
trace and log hash. Inspect whether expected tests ran; a later successful
command cannot repair an earlier failure. Unknown dependency scope needs rechecking.
Changed bytes, configuration, registry or normative basis invalidate affected
evidence. A required unavailable check blocks; omission cannot make it green.

Final checks use fresh `final_verifier` roles and a final-HEAD snapshot separate
from historical task candidates. Earlier logs do not replace that final run.
