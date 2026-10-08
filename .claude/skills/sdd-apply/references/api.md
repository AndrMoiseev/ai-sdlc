# Script and event contract

Read the installed `scripts/lib/api.py` for the currently exported operations and exact argument names. Call them through `execute.py --request`, with JSON shaped as `{"operation":"<name>","args":{...}}`. A missing mandatory operation is a package implementation gap: stop that step and report it. Do not substitute hand-edited state, hand-built dashboards, or handwritten Git orchestration.

`validate` accepts `project_root`, optional `change`, `instruction: {text, source}`, and optional `sdd_spec`. Preserve its returned basis. It invokes the companion's check/snapshot interfaces and checks both document and plan approval. An ambiguous change requires selection; missing approval or a missing plan returns to sdd-spec.

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

Use JSON null for run-level `task_id`. Read the current revision before a new event. Retry a lost response with the identical event; a new payload needs a new ID and current revision. A rejected event does not authorize side effects. Re-read after revision conflict. Recover a lock only through the script's owner-liveness check; elapsed age is not evidence of death.

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
| `budget_extend` | `budget: review|test`, new finite `limit`, explicit user decision `source` and `text`. |

Task states are `pending`, `running`, `verifying`, `reviewing`, `integrating`, `repairing`, `committing`, `blocked`, `accepted`. Run states are `active`, `blocked`, `completed`. Executor DONE and exit 0 alone satisfy neither acceptance nor completion.

The transition router also recognizes `resume`, `spec_conflict`, `revised_plan`, `handoff`, `mode`, and `finalize`. Read their installed handler schemas before constructing payloads. Mode-specific events belong only in the selected mode flow.

`finalize` defers all technical debt when `recommendation_decisions` is omitted.
Explicit decisions must cover every journal `finding_id` once, with `action:
defer|reject` and a `reason`. A `fix` decision is not accepted during plan
finalization: summarize debt after completion and obtain explicit user approval
for scoped follow-up work under the [review policy](review-policy.md).

## Evidence

Register exact commands, cwd, configuration, source, and AC before implementation, including project instructions and CI. Existing mandatory checks remain mandatory. An absent applicable linter is an explained inventory fact, not a successful run. `setup_required` permits preparing a concrete runner inside that task; it does not permit reducing assertions or editing the approved plan. Record before/after setup and run existing checks independently. Final checks use `final_verifier` and capture a final-HEAD snapshot separately from historical task candidates.

Retain command, stdout/stderr, exit code, duration, source snapshots, role launch trace, and log hash. Use each command's actual exit status: a later successful shell command cannot repair an earlier failure. Review whether the expected tests actually ran. Unknown dependency scope requires rechecking. Any change to checked bytes, configuration, registry, or normative basis invalidates affected evidence. A required unavailable check blocks; it never becomes green by omission.

Only orchestrator-authorized script events write state. A launched verifier can invoke the CLI with the run's owner identity for its assigned `check_run`; otherwise it requests that exact operation through the orchestrator. Retain the real role request and corresponding tool trace. The owner string is process coordination, not authentication. Registering a role ID and executing commands without launching that role is not independent verification.
