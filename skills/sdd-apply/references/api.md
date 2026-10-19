# Script and event contract

`resolve_agent` is a read-only operation: pass execution `directory`, role `kind`,
`host`, observed `parent_model`, optional `parent_effort`, and for Claude Code the
observed `available_agents` array. It uses the stored project root and sdd-shared
dependency. Retain its result as `agent_selection` in `role_register`; see
[subagent selection](subagents.md). It selects parameters, not a running agent.
Optional `model_observation` records actual model/effort and source trace; unknown
values are null. Old registrations remain valid. New registrations with a project
settings file require selection evidence and reject conflicting shared contexts.

Read the installed `scripts/lib/api.py` for the currently exported operations and exact argument names. Call them through `execute.py --request`, with JSON shaped as `{"operation":"<name>","args":{...}}`. A missing mandatory operation is a package implementation gap: stop that step and report it. Do not substitute hand-edited state, hand-built dashboards, or handwritten Git orchestration.

`validate` accepts `project_root`, optional `change`, `instruction: {text, source}`, and optional `sdd_shared`. Legacy `sdd_spec` locates sdd-shared alongside that path; supply only one explicit selector. Preserve its returned basis. It invokes the companion's check/snapshot interfaces and checks both document and plan approval. An ambiguous change requires selection; missing approval or a missing plan returns to sdd-spec.

Public operations are `initialize` (validation arguments plus `owner`, optional `parallel_request` and `isolation`), `read`, `available`, `dashboard`, `recover_lock`, `serve`, and `stop_server` (each takes `directory`; `serve` also accepts `port`, default 0). `event` takes `directory` and `event`. `initialize` validates, records a new run and generates the initial dashboard; `read` verifies integrity. Existing state requires resume. The script owns all state writes and generated views. Verify these operations exist in the installed API before use.

Every applied event has exactly these fields:

```json
{
  "event_id": "unique-operation-id",
  "run_id": "saved-run-id",
  "expected_revision": 0,
  "owner": "registered-orchestrator-context",
  "type": "event-name",
  "task_id": "TASK-ID-or-null",
  "payload": {}
}
```

Use JSON null for run-level `task_id`. Read the current revision before a new event, using the read view below. Retry a lost response with the identical event; a new payload needs a new ID and current revision. A rejected event does not authorize side effects. Re-read after revision conflict. Recover a lock only through the script's owner-liveness check; elapsed age is not evidence of death.

## Read views

For routine revision refreshes in an active session, including after a revision
conflict, request `{"operation":"read","args":{"directory":"<execution>","view":"compact"}}`.
Both views validate the entire state, registered root, integrity and event chain
before returning. The default `view: "full"` preserves the original response.

| Need | View |
|---|---|
| Current revision, task status, blockers, budgets or active role IDs | `compact` |
| Resume, handoff, lost response/effect investigation or debugging | `full` |
| Candidate, checks, evidence, review findings, plan, authorization or any omitted detail needed for the next event | `full`; read the referenced original artifacts as required by the flow |

Compact view version 1 returns run identity, owner, revision, status, mode and
timestamp; each task's status, attempt, complete blockers, review/test budget
counters and active reservations; active role IDs with task/kind/context; and
`available_tasks` from the existing scheduler. Artifact paths are relative to
the execution directory: `state` is the full saved state and `run` contains its
role packets, logs and effect journals. Use API `read` for verified full state.
Historical roles, events, plans, candidates, checks, evidence and reviews remain
in full state and artifacts, and are not repeated in compact output.

`available_tasks` indicates dependency/mode eligibility only. It does not check
all start prerequisites or authorize any event. Active roles are recorded
identities, not a liveness check. Neither view proves that candidate bytes,
approvals or evidence remain current; the existing event handlers enforce their
gates. Use the selected flow and current user authorization for the next action.
Keep the original event envelope for an idempotent retry, including its original
revision; never replace it with the revision from a newer compact read.

## Task events

| Event | Required payload or effect |
|---|---|
| `checks_register` | `inventory: {instructions: [...], ci: [...]}`, `additional: [...]`; before start, preserve planned commands and source/AC mappings. Explicit empty inventories are valid. |
| `role_register` | `role_id`, `kind`, `context_id`, `fresh: true`, `host`, `launch_ref`, `capabilities: {fresh_context: true}`. Returns the role packet path. |
| `start` | `role_id`, explicit owned `paths`; requires generated initial dashboard, registry, eligible task and active executor. |
| `check_run` | `role_id`, `stage`, optional `timeout`; stages are `baseline`, `self`, `independent`, `integration`, `final`. The script runs the complete registry and saves raw results. |
| `check_setup` | `check_id`, exact `command`, `description`, optional `cwd` and `configuration`; only for planned unresolved setup/procedure during running or repairing, after baseline capture. |
| `checks_extend` | After `more_checks`, supply `review_round` and `additional` runnable checks. Existing checks remain mandatory; the updated registry invalidates earlier verification. |
| `procedure_begin`, `procedure_result` | For a registered `run.procedure`, begin with `check_id`, `role_id`, `stage`. Execute the referenced procedure in that role. Return the same IDs plus `outcome`, actual `steps` and host `trace`; then `check_run` reconciles the entire assigned set. Script snapshots detect edits during the procedure; its semantic result is a role attestation, not inferred from exit 0. |
| `role_result` | `role_id`, structured `result`, actual host `trace`; ends role work, never accepts a task. |
| `candidate` | Freeze the candidate after executor result; evidence binds source, normative manifest, registry, and root. |
| `review_start` | Independent reviewer `role_id`; reserves one task-lifetime review round after passing verification. |
| `review_result` | `role_id`, exact `candidate`, `verdict: pass|changes|more_checks`, `findings`, `test_integrity`, `trace`. Findings follow the [review policy](review-policy.md): only structured `proof` admits a blocker; unsupported findings become recommendations, and `changes` with no proven blockers becomes `pass`. |
| `repair` | `reason`, defect evidence or recorded failure, optional successor `executor`; pass `test_failure: true` for a failed self-check so the test budget is reserved. |
| `commit`, `accept` | Script gates current evidence, passing review and task ownership; commit precedes acceptance. |
| `block` | `reason`, `resume_condition`; preserve partial work and evidence. |
| `worktree_refresh` | `reason`, `evidence` of the fixed execution base; replaces an unfinished, unintegrated task worktree at current HEAD and preserves its work and budgets. Stop task roles and resolve existing run blockers first. See [worktree recovery](worktree-recovery.md). |
| `worktree_refresh_resolve` | `intent_id`, finished resolver `role_id`, `resolution`; adopts a resolved replacement from a conflicted refresh, verifies preservation and completes old-worktree cleanup. |
| `budget_extend` | `budget: review|test`, new finite `limit`, explicit user decision `source` and `text`. |

Task states are `pending`, `running`, `verifying`, `reviewing`, `integrating`, `repairing`, `committing`, `blocked`, `accepted`. Run states are `active`, `blocked`, `completed`. Executor DONE and exit 0 alone satisfy neither acceptance nor completion.

The transition router also recognizes `resume`, `spec_conflict`, `revised_plan`, `handoff`, `mode`, and `finalize`. Read their installed handler schemas before constructing payloads. Mode-specific events belong only in the selected mode flow.

`finalize` defers all technical debt when `recommendation_decisions` is omitted.
Explicit decisions must cover every journal `finding_id` once, with `action:
defer|reject` and a `reason`. A `fix` decision is not accepted during plan
finalization: summarize debt after completion and obtain explicit user approval
for scoped follow-up work under the [review policy](review-policy.md).

## Evidence

Read the installed sdd-shared's `references/document-format-tasks.md`, section «Задача и ее проверка», for the shared verification contract. `location` identifies the file/directory defining the check, relative to the project or active worktree root, independently of command cwd. The scripts use the companion's path validator. At check_run, require its location to be a file or directory for every run variant; a missing location yields `unavailable`, even when the command would exit 0 or a procedure result reports success. Additional registry checks may omit location; when supplied, it follows the same contract. A directory's existence does not prove that the expected tests ran.

Register exact commands, cwd, configuration, source, and AC before implementation, including project instructions and CI. Existing mandatory checks remain mandatory. An absent applicable linter is an explained inventory fact, not a successful run. `setup_required` permits creating a planned check or preparing its runner inside that task, including a future test with a known command. Only unresolved setup_required is `planned_absence` at baseline. A missing location under command/procedure blocks; return an incorrectly planned future check to sdd-spec rather than changing the approved run. Record before/after setup and run existing checks independently; setup does not permit reducing assertions. Final checks use `final_verifier` and capture a final-HEAD snapshot separately from historical task candidates.

Every `command`, including additional checks and `check_setup`, uses the shared argument-array contract. The runner passes this array unchanged with `shell=False` and records it in evidence. Register a required interpreter explicitly; never silently wrap a string in `sh -c` or `cmd /c`. Legacy string commands are rejected at registration; persisted strings yield `unavailable` with `limitation: command_format` when run. Preserve old execution evidence and return an incompatible approved plan for revision; changing command representation invalidates the registry/candidate and requires fresh checks.

Retain command, stdout/stderr, exit code, duration, source snapshots, role launch trace, and log hash. Use each command's actual exit status: a later successful shell command cannot repair an earlier failure. Review whether the expected tests actually ran. Unknown dependency scope requires rechecking. Any change to checked bytes, configuration, registry, or normative basis invalidates affected evidence. A required unavailable check blocks; it never becomes green by omission.

Only orchestrator-authorized script events write state. A launched verifier can invoke the CLI with the run's owner identity for its assigned `check_run`; otherwise it requests that exact operation through the orchestrator. Retain the real role request and corresponding tool trace. The owner string is process coordination, not authentication. Registering a role ID and executing commands without launching that role is not independent verification.
