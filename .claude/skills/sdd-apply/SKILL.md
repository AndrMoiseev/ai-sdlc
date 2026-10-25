---
name: sdd-apply
description: Execute an approved sdd-spec plan when the user explicitly invokes sdd-apply. Supports starting, resuming, and accepting implementation work. Not for drafting specifications or OpenSpec workflows.
disable-model-invocation: true
---

# SDD Apply

Use only on explicit invocation. Keep normative SDD documents unchanged.

Only when changing the sdd-apply skill itself, read
[maintenance and test rules](references/maintenance.md) before editing or testing.
Leave that reference unloaded when using sdd-apply to implement another project.

Before each fresh worker launch, apply [project subagent selection](references/subagents.md).
Resolve the role's agent from `.sdd/settings.json` at the execution's original project root.

## Coordination and progress

Before coordinating workers, read the [shared coordination contract](../sdd-shared/references/coordination.md).

## Skill development acceptance

When creating or changing skills, accept each individual planned task using only
deterministic tests. Schedule all behavioral checks, including agent-based evals,
trigger tests and pressure scenarios, exclusively for final acceptance of the
whole plan. Apply this boundary to baseline, self-checks, independent verification,
integration and repair retries as well. If the approved plan requires a behavioral
check before final acceptance, return that conflict to sdd-spec before execution;
do not silently omit the check or replace it with a deterministic test.

## Route

1. Before execution, read [runtime setup](references/runtime-setup.md), [API contract](references/api.md), and the host adapter: [Codex](agents/codex.md), [Claude Code](agents/claude-code.md), or [arbitrary agent](agents/generic.md) when neither host is established.
2. For an existing execution, read [resume](flows/resume.md). For a new execution, read [start](flows/start.md).
3. Select one mode from verified state and the current user's authorization. For a new execution, default to `parallel` when isolation is available; invoking sdd-apply authorizes this mode without a separate parallel request. Use `sequential` when the user explicitly requests it or isolation is unavailable, explaining the fallback. For an existing execution, preserve its saved mode unless the user changes it; apply the resume handoff contract for any mode change.
4. Load only [execute-sequential](flows/execute-sequential.md) or [execute-parallel](flows/execute-parallel.md). Keep the other flow unloaded.
5. Before acting on code-review findings, read [review policy](references/review-policy.md). For a failed check or proven review violation, read [repair](flows/repair.md). For a normative conflict, use [resume](flows/resume.md). After all tasks are accepted, read [finalize](flows/finalize.md).

If a loaded mode must change, transfer ownership to a fresh context through the resume flow. Authorization to execute includes local task commits; delivery beyond those commits requires its own instruction.
