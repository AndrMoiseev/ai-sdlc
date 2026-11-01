---
name: sdd-apply
description: Execute an approved sdd-spec plan on explicit invocation or after the user approves the current plan in sdd-spec. Supports starting, resuming, and accepting implementation work. Not for drafting specifications or OpenSpec workflows.
disable-model-invocation: false
---

# SDD Apply

Start on explicit invocation or a verified current plan approval handed off by sdd-spec. Plan approval authorizes execution unless the user explicitly withheld it; follow the [shared approval contract](../sdd-shared/references/document-format-review.md#опциональное-ревью-и-разрешение-на-реализацию). Keep normative SDD documents unchanged.

Before starting or resuming, exclude transient execution files from Git using
the [runtime setup policy](references/runtime-setup.md#transient-execution-files).

Only when changing the sdd-apply skill itself, read
[maintenance and test rules](references/maintenance.md) before editing or testing.
Leave that reference unloaded when using sdd-apply to implement another project.

Before each fresh worker launch, apply [project subagent selection](references/subagents.md).
Resolve the role's agent from `.sdd/settings.json` at the execution's original project root.

## Coordination and progress

Before coordinating workers, read the [shared coordination contract](../sdd-shared/references/coordination.md).

## Skill development acceptance

Use deterministic tests for task acceptance when changing skills. Run behavioral,
trigger and pressure evals only as separately authorized evaluation work outside
this task flow. There is no automatic final evaluation phase.

## Route

1. Before execution, read [runtime setup](references/runtime-setup.md), [API contract](references/api.md), and the host adapter: [Codex](agents/codex.md), [Claude Code](agents/claude-code.md), or [arbitrary agent](agents/generic.md) when neither host is established.
2. For an existing execution, read [resume](flows/resume.md). For a new execution, read [start](flows/start.md).
3. Execute independent tasks in parallel using isolated task worktrees. Invoking sdd-apply authorizes this execution without a separate parallel request. Unavailable isolation blocks execution. Unsupported legacy execution states must be reconciled with their original skill version; do not rewrite their mode.
4. Read [execute-parallel](flows/execute-parallel.md).
5. Before acting on code-review findings, read [review policy](references/review-policy.md). For a failed independent check after executor completion or proven review violation, read [repair](flows/repair.md). Executor self-checks remain within implementation and do not consume the failure budget. For a normative conflict, use [resume](flows/resume.md). After all tasks are accepted, read [finalize](flows/finalize.md).

Authorization to execute includes local task commits; delivery beyond those commits requires its own instruction.

When refactoring changes module boundaries and their tests, apply the
[test evolution policy](references/review-policy.md#tests-at-changed-module-boundaries).

## Execution and assessment

After the executor reports completion, freeze its commit and direct Explorer to
execute the full project test and static-check set under
[role coordination](references/role-coordination.md#explorer-dispatch). Explorer
executes the exact assignment and reports results; the orchestrator selects and
registers the complete set. Only after it passes, launch the required
[review lenses](references/review-policy.md#review-lenses) in parallel, each in its
own fresh context. Reviewers inspect sources and saved evidence without executing
checks. Manual and behavioral checks are outside this task flow. Complete the plan
from accepted tasks using [finalize](flows/finalize.md).
