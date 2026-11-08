# Worker coordination

## Workflow ownership

Role instructions define the nature of the work, autonomy boundaries and result
quality. The calling workflow defines phases, documents, checks, when to launch,
continue or replace a worker, and context isolation or reuse. The orchestrator
executes that workflow: it assigns scope, handles user decisions and checks the
conditions for each transition. A shared role or selected profile does not grant
additional workflow permissions.

## Results and evidence

Record the worker's actual result separately from the orchestrator's assessment.
Distinguish a completed portion, missing facts or decisions, and a blocker. A
dispatch, progress message or earlier completion does not establish the result
of the current assignment. Preserve the assignment identity, input basis, actual
output references and limitations required by the calling workflow.

Compare the returned changes with the assigned scope and basis. Changed input
decisions or unrelated edits can make dependent work stale; retain the candidate
and reconcile it against current inputs before relying on it. Expected worker
output changes are not themselves stale inputs: distinguish the input basis from
the completed output version. Successful writing or command execution does not
establish approval or acceptance.

## Writing and handoff

Assign one writer at a time to each output area. Workers preserve others' changes;
overlapping writes or changed input decisions stop dependent writing until the
orchestrator reconciles the assignment.

Before handing write authority to another worker or applying an authorized patch,
obtain the completed portion and confirmation that the previous writer has stopped.
Confirm a departing writer's stopped state through the host before a successor
writes. Unknown write state blocks transfer of write authority. Checks, review or
checkpoints that require a stable version use the completed portion under the
calling workflow's rules. Retain completed work when a new user instruction changes
or cancels the assignment; resume dependent writing only under the current assignment.

## Messages and waiting

Include this messaging rule in worker assignments: send the result, a blocker,
or a request for a needed decision; return required reports and evidence in full.
Receive results through host notifications. Query status for a concrete delivery
problem, recovery, or signs of a lost agent; repeat a status request only with
new grounds. Keep required launch handshakes and role operations.

When independent work is exhausted, wait for events with
a timeout of at least 10 minutes (600 seconds; `collaboration.wait_agent`:
`timeout_ms: 600000`, when available). Handle a notification or user input as soon
as the tool returns. For a stricter host limit or a required user update deadline,
split the waiting interval into shorter calls; use a confirmed equivalent tool
on other hosts. If notifications are unavailable, query status after waiting.
A timeout alone means no event arrived; it proves neither completion nor failure.
Continue or replace the worker only under the calling workflow's rules and actual
host evidence.

Keep intermediate user updates to one or two sentences: the material change and
next step. If an update is due without new events, briefly name what is pending.
Expand for blockers or user decisions; retain the calling flow's full reports,
evidence, approvals and final response requirements.

## Explorer evidence

For explorer work, hand off the saved assignment and actual result references
under [the explorer contract](explorer.md). At the step defined by the calling
workflow, the orchestrator forwards the machine summary, current basis and primary
evidence references to the assigned assessor. Explorer conversation is not evidence
for that assessment. The assessor opens needed raw artifacts. Reading an artifact
does not require rerunning its command. A requested rerun returns through the
orchestrator and the owning workflow's existing budgets and execution permissions.
