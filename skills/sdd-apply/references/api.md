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
  "owner": "registered-orchestrator-context",
  "type": "event-name",
  "task_id": "TASK-ID-or-null",
  "payload": {}
}
```

Use JSON null for run-level `task_id`. Read current revision before a new event.
Retry a lost response with the identical envelope, including its original
revision; a changed payload needs a new ID and current revision. Re-read after
revision conflict. A rejected event authorizes no side effects. Recover a lock
only through the script's owner-liveness check; age alone proves nothing.

## Read views

For routine revision refreshes, including after revision conflict, use
`{"operation":"read","args":{"directory":"<execution>","view":"compact"}}`.
Both views validate the entire state, registered root, integrity and event chain.
The default `view: "full"` preserves the complete response.

| Needed information | View |
|---|---|
| Revision, task status, blockers, budgets, active role IDs | `compact` |
| Resume, handoff, lost response/effect investigation or debugging | `full` |
| Candidate, checks, evidence, findings, plan or authorization absent from compact | `full`, then referenced original artifacts |

Compact view version 1 returns run identity/owner/revision/status/mode/time,
task statuses and complete blockers/budget counters/reservations, active role
IDs with task/kind/context, `available_tasks`, and artifact paths relative to the
execution directory. Historical events, roles, plans and evidence stay in full
state and artifacts. Use API `read` for verified full state.

`available_tasks` reports dependency/mode eligibility, not admission permission.
Active role IDs are not a liveness check. Neither view proves candidate bytes,
approvals or evidence current; transition handlers enforce their own gates.
Executor DONE and exit 0 alone establish neither acceptance nor completion.

Only orchestrator-authorized events write state. A launched verifier may use the
run's owner identity for its assigned `check_run`; otherwise it requests that
operation from the orchestrator. Keep the actual role request and tool trace.
The owner string coordinates processes; it is not authentication. Registering a
role without launching it is not independent verification.
