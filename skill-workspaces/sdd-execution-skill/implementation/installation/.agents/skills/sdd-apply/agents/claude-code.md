# Claude Code adapter

Apply [role contract](../references/roles.md). Explicit invocation is enforced by `disable-model-invocation: true` in SKILL.md.

Discover the host's actual native agent/task tool and launch a new context without inherited author conversation. Pass only role, task paths, file boundaries and the waiting handshake; record the actual host identity and launch trace. Register it, then deliver the generated packet through the tool's supported messaging mechanism. Check actual file access and inherited project/user instructions.

Use the configured host model unless the user authorizes another. Retain native launch, command and result traces. Distinguish busy slots from an absent fresh-context mechanism or a lost agent. If the tool cannot demonstrate fresh context, use a clean CLI session only after runtime probes establish version, existing login, isolation and workspace access. Do not invent tool flags or report a simulated adapter test as native execution.

For a mode handoff, use a fresh context and transfer only saved state, common contracts and the newly selected flow. Preserve one orchestrator owner throughout the transfer.
