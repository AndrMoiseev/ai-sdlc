# Project subagent selection

Before a new explorer, executor, verifier or reviewer launch, read
[the shared subagent contract](../../sdd-shared/references/subagents.md) in the
sibling `sdd-shared` package. If it is missing, stop with a critical dependency error.
That shared contract defines `.sdd/settings.json`, the role registry, host behavior,
fallbacks and source evidence. Read that reference directly; do not invoke the
authoring workflow. Update the SDD bundle together.

Use the [API](api.md) operation `resolve_agent` before the waiting handshake:

```json
{
  "operation": "resolve_agent",
  "args": {
    "directory": "<change-root>/execution",
    "kind": "reviewer",
    "host": "codex",
    "parent_model": "<observed-parent-model>",
    "parent_effort": "<observed-parent-effort>"
  }
}
```

For Claude Code use `host: claude-code` and `available_agents`, an array of names
observed in its actual tool/catalog. The operation always uses `basis.project_root`,
not the task worktree. It returns launch parameters and evidence without spawning.
Pass the complete result as `agent_selection` when registering the observed launch.
Configuration errors or an unavailable requested launch capability block that role.

Verifier/reviewer context sharing requires equal resolved launch identities. Compare
their selections before spawning; differing models, effort or native agent definitions
require separate contexts. Registration checks this invariant as well.
Claude Code native-agent selections always use separate verifier/reviewer contexts;
their name-only catalog cannot prove equal definition versions. Existing
registrations without selection evidence remain readable; with settings.json present,
new registrations require selection evidence. Interrupted launches with changed source
hashes require reconciliation, not invented attestations or duplicate writers.

Repair and continuation retain the running executor's selection. Reconfigure only a
fresh successor through role registration and resume reconciliation.
Record actual model observations separately from requested
parameters. These changes leave task budgets, approvals and independent checks intact.
