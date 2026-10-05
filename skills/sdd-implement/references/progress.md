# Durable progress and human verification

Keep a concise `autopilot-progress.md` beside the resolved change artifacts, respecting planning-root edit constraints. Reuse an existing equivalent record if one exists. This supplements the authoritative task plan; it never replaces specifications, CLI readiness, or Git evidence.

## Record contents

- Change identifier, selected store if any, schema, implementation repository, planning root, branch, original baseline commit, and role settings/overrides.
- Required automatic-check commands, working directories, applicability, wall-clock deadlines and their basis, elapsed times, and evidence for the candidate they validated. For timeouts, retain the last active test/package, diagnostic-log location, process cleanup result, and next diagnostic action.
- Per task: stable task ID, requirements/acceptance references, dependencies, implementation/review status, task base, implementation commit, correction commits, completed correction-cycle count, agent identities, unresolved findings, and next action.
- Findings: ID, review origin, severity, critical/technical-debt classification and rationale, evidence, affected task, disposition, and commit addressing it where applicable. Link deferred finding IDs to the technical-debt journal rather than duplicating its details.
- Ordinary blockers and exact missing input; distinguish a task-level blocker from a global stop.
- Final candidate commit, final review status/findings, manual-plan path, technical-debt journal path and open count, and whether human execution remains pending.

Useful review states are `not_started`, `implementing`, `awaiting_review`, `correcting`, `accepted`, `accepted_with_technical_debt`, and `blocked`. Global outcomes include `in_progress`, `blocked`, `stopped_after_task_review`, `stopped_after_final_review`, and `autonomous_complete`. Track human execution independently as `not_run`, `passed`, or `failed`.

Save after implementation commits, review results, correction commits, blocker changes, and before yielding. If a review request is pending, record its candidate and cycle so resuming does not consume another cycle. A restart never resets the three-cycle counter.

Include task plan/manual instructions and progress known before a commit in the corresponding task or correction commit when they belong to that repository. Commit hashes and later review outcomes are necessarily recorded afterward. They may remain as explicitly reported local planning changes and join the next authorized task/correction commit. Do not create empty commits or rewrite commits to insert their own hashes. The final report must identify any uncommitted planning records. If planning lives in another repository, preserve its local records; do not assume authorization to create extra commits there.

## Resume reconciliation

1. Read current task artifacts and this record, then inspect Git status, branch, log, and recorded commit ancestry. Preserve the original baseline across ordinary continuations.
2. Verify implementation and correction commits exist and belong to the selected change. Reconstruct a missing post-commit checkpoint from attributable Git evidence; do not duplicate a commit because the journal update was interrupted.
3. A checked task without review evidence still needs review. A committed candidate with a pending review resumes at review. An uncommitted correction resumes with check/commit rather than dispatching a second implementation. Count correction commits and completed rereviews separately to avoid an off-by-one cycle.
4. If code, requirements, or branch history changed, identify affected acceptance/check/review evidence and invalidate it. Recheck and rereview affected work before claiming completion. Ask only when attribution, intended scope, or the baseline cannot be resolved safely.
5. For tasks completed before this workflow began, identify their original commit range when possible and review the existing implementation without creating empty commits. If the full change range cannot be established, report the gap and resolve it before claiming a final review of the entire change.
6. Reconcile legacy `substantial`/`non-substantial` classifications and `accepted_with_minor_findings` states against the current review threshold using saved evidence. Preserve findings and cycle counts; move non-critical findings into the technical-debt journal. A saved global stop remains stopped if critical findings or execution blockers remain; present those blockers and await explicit direction. If the stop was solely for findings now classified as technical debt, record the reclassification and resume remaining validation/review work. A generic invocation is not authorization to automatically fix critical final-review findings.

## Technical-debt journal

On the first deferred finding, create `technical-debt.md` beside the resolved change artifacts, respecting planning-root edit constraints, or reuse an existing dedicated journal for this change. Persist each deferred finding when its review returns, including findings from final review. Record:

- Stable finding ID, originating task/review, and affected file/location.
- Potential problem, evidence or reproduction, expected impact, and assumptions about its trigger or likelihood.
- Why it falls below the critical threshold, a possible follow-up, and status (`open`, `resolved`, or `promoted_to_critical`).

Merge repeated findings about the same underlying problem across tasks and review cycles, preserving origins and IDs as aliases. Update existing entries instead of appending duplicates. Preserve the journal on resume, and mark resolutions or promotions with supporting evidence. Count only distinct `open` entries for the selected change; resolved and promoted entries are excluded. Deferred debt alone does not trigger fixes, correction cycles, task reopening, or a global stop.

Apply the same commit/local-record rules as progress files. At completion, present debt to the user only as the journal link and open potential-problem count; keep finding details in the file. If no journal is needed, report zero. If an existing journal has no open entries, retain its history and report its link with zero.

## Manual checks

When a task needs human verification, add a small manual-check block directly under that task in the authoritative plan, using its existing format. Include a stable case ID, linked requirement, prerequisites/environment/test data, exact numbered actions, observable expected results, and execution status. Include cleanup only where the test creates state needing cleanup.

At the end, create or update `manual-test-plan.md` in the resolved change directory, or use its existing manual plan. Consolidate every task's cases with links back to its task and preserve matching case IDs. Check the task cases and consolidated plan agree. Do not create a manual plan when no manual checks are needed.

A task that specifically requires a human to execute a check remains pending execution; completing its test instructions does not justify checking it off. Pending human execution does not block implementation, commits, task progression, or final review. Report autonomous completion separately from full plan execution when those statuses differ.
