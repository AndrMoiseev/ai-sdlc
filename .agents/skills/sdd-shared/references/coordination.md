# Worker coordination

Include this messaging rule in worker assignments: send the result, a blocker,
or a request for a needed decision; return required reports and evidence in full.
Receive results through host notifications. Query status for a concrete delivery
problem, recovery, or signs of a lost agent; repeat a status request only with
new grounds. Keep required launch handshakes and role operations.

When independent work is exhausted in sdd-spec or sdd-apply, wait for events with
a timeout of at least 10 minutes (600 seconds; `collaboration.wait_agent`:
`timeout_ms: 600000`, when available). Handle a notification or user input as soon
as the tool returns. For a stricter host limit or a required user update deadline,
split the waiting interval into shorter calls; use a confirmed equivalent tool
on other hosts. If notifications are unavailable, query status after waiting.
A timeout alone means no event arrived: continue waiting with the same agent.

Keep intermediate user updates to one or two sentences: the material change and
next step. If an update is due without new events, briefly name what is pending.
Expand for blockers or user decisions; retain the calling flow's full reports,
evidence, approvals and final response requirements.

For explorer work, hand off the saved assignment and actual result references
under [the explorer contract](explorer.md). The orchestrator forwards the machine
summary, current basis and primary evidence references to an independent verifier;
explorer conversation is not verification input. The verifier opens needed raw
artifacts and assesses criteria. Reading an artifact does not require rerunning
its command. A requested rerun returns through the orchestrator and the owning
workflow's existing budgets and execution permissions.
