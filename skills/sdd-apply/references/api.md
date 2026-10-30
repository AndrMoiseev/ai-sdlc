# Script and event contract

Call `execute.py --request <file>` with
`{"operation":"<name>","args":{...}}`. The script owns state writes, Git effects
and generated views. Read this contract once per context; load details for the
current step:

| Step | Contract |
|---|---|
| Validate or initialize an execution | [Start API](api-start.md) |
| Register/run checks, freeze a candidate, assess evidence | [Checks and evidence](api-checks.md) |
| Start, review, repair, commit or accept a task | [Task events](api-tasks.md) |
| Select or launch a worker | [Subagent selection](subagents.md), [role coordination](role-coordination.md) |
| Resume, revise the plan or hand off ownership | [Resume](../flows/resume.md) |
| Complete the run | [Finalize](../flows/finalize.md) |

For exact installed arguments use `execute.py --help-operation <name>` or
`execute.py --help-event <type>`. The read-only request equivalent is
`{"operation":"help","args":{"event":"resume"}}`; use `operation` instead
of `event` for a public operation, or empty args to list both. A missing required
operation is a package gap: report it and stop that step. Help describes inputs,
not permission to transition. Preserve the calling flow's gates.

## Event envelope

`event` accepts `directory` and this complete `event` object:

```json
{
  "event_id": "unique-operation-id",
  "run_id": "saved-run-id",
  "expected_revision": 0,
  "type": "event-name",
  "task_id": "TASK-ID-or-null",
  "payload": {}
}
```

Use JSON null for run-level `task_id`. Read current revision before a new event.
Initialization and new event envelopes no longer accept `owner`; the `handoff`
event is removed. Historical state and event records remain readable unchanged.
Reconcile pending effects and lost responses with their original runtime before
upgrading: an old envelope containing `owner` cannot be retried through this API.
Retry a lost response with the identical envelope, including its original
revision; a changed payload needs a new ID and current revision. Re-read after
revision conflict. A rejected event authorizes no side effects. Recover a lock
only through the script's owner-liveness check; age alone proves nothing.

## Read views

For routine revision refreshes, including after revision conflict, use
`{"operation":"read","args":{"directory":"<execution>","view":"compact"}}`.
The default is `view: "compact"`. Both views validate the current manifest,
registered root, history head and accessed objects. `view: "full"` returns the
stored manifest with references; it does not expand the execution history.

| Needed information | View |
|---|---|
| Revision, task status, blockers, budgets, active role IDs | `compact` |
| Explorer scope/stage/status and separate execution/conclusion status | `compact`: `explorer_assignments`, `tasks[id].verification` |
| Resume, lost response/effect investigation or debugging | `full`, then only relevant referenced objects |
| Checks, evidence, findings, plan or authorization absent from compact | `full`, then `read_object` for the relevant reference |

Compact view version 1 returns run identity/revision/status/time,
task statuses and complete blockers/budget counters/reservations, active role
IDs with task/kind/context, `available_tasks`, and artifact paths relative to the
execution directory. Historical events and large values live in immutable objects.
A `{"$object": {"path": "objects/...json", "sha256": "...", "bytes": 123,
"kind": "object"}}` value is a reference. Pass its inner descriptor to
`{"operation":"read_object","args":{"directory":"<execution>","reference":{...}}}`.
The response verifies and returns one object, retaining nested references.
Read only objects needed for the current decision; do not recursively expand
the manifest into the model context. `initialize` returns the full manifest;
event results also keep large values behind references.

Use `{"operation":"audit","args":{"directory":"<execution>"}}` for a full
integrity audit of current objects, the entire event chain and event-ID index.
The script runs this audit before `resume` and `finalize`. Ordinary reads do not
claim to detect corruption in unaccessed historical objects. See
[state storage](state-storage.md) for commit boundaries and recovery.

`available_tasks` reports dependency/conflict eligibility, not admission permission.
Active role IDs are not a liveness check. Neither view proves candidate bytes,
approvals or evidence current; transition handlers enforce their own gates.
Executor DONE and exit 0 alone establish neither acceptance nor completion.

Only orchestrator-authorized events write state. A launched explorer with a matching
checks assignment may submit its assigned `check_run`; otherwise it requests that
operation from the orchestrator. Keep the actual role request and tool trace.
Registering a role without launching it is not independent verification. The verifier
assesses saved evidence and submits a separate `verification_result`; it does not
execute deterministic checks.
