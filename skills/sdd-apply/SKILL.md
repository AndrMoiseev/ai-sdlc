---
name: sdd-apply
description: Execute an approved sdd-spec plan when the user explicitly invokes sdd-apply. Supports starting, resuming, and accepting implementation work. Not for drafting specifications or OpenSpec workflows.
disable-model-invocation: true
---

# SDD Apply

Use only on explicit invocation. Keep normative SDD documents unchanged.

Before each fresh worker launch, apply [project subagent selection](references/subagents.md).
Resolve the role's agent from `.sdd/settings.json` at the execution's original project root.

## Coordination and progress

Include this messaging rule in worker assignments: send the result, a blocker,
or a request for a needed decision; return required reports and evidence in full.
Receive results through host notifications. Query status for a concrete delivery
problem, recovery, or signs of a lost agent; repeat a status request only with
new grounds. Keep required launch handshakes and role operations.

When independent work is exhausted, wait for events with a 120-second timeout
(`collaboration.wait_agent`: `timeout_ms: 120000`, when available). Handle a
notification or user input as soon as the tool returns. Shorten the wait for a
stricter host limit or a required user update deadline; use a confirmed equivalent
tool on other hosts. If notifications are unavailable, query status after waiting.
A timeout alone means no event arrived: continue waiting with the same agent.

Keep intermediate user updates to one or two sentences: the material change and
next step. If an update is due without new events, briefly name what is pending.
Expand for blockers or user decisions; retain the flow's full reports, evidence,
approvals and final response requirements.

## Route

1. Before execution, read [runtime setup](references/runtime-setup.md), [API contract](references/api.md), and the host adapter: [Codex](agents/codex.md), [Claude Code](agents/claude-code.md), or [arbitrary agent](agents/generic.md) when neither host is established.
2. For an existing execution, read [resume](flows/resume.md). For a new execution, read [start](flows/start.md).
3. Select one mode from verified state and the current user's authorization. Default to `sequential`. Select `parallel` only with an explicit scoped request and available isolation. If isolation is unavailable, select `sequential` before loading a mode flow and explain why.
4. Load only [execute-sequential](flows/execute-sequential.md) or [execute-parallel](flows/execute-parallel.md). Keep the other flow unloaded.
5. Before acting on code-review findings, read [review policy](references/review-policy.md). For a failed check or proven review violation, read [repair](flows/repair.md). For a normative conflict, use [resume](flows/resume.md). After all tasks are accepted, read [finalize](flows/finalize.md).

If a loaded mode must change, transfer ownership to a fresh context through the resume flow. Authorization to execute includes local task commits; delivery beyond those commits requires its own instruction.
