# Claude Code adapter

Apply [role contract](../references/roles.md). Explicit invocation is enforced by `disable-model-invocation: true` in SKILL.md.

Discover the host's actual native agent/task tool and available agent catalog. Resolve [project subagent selection](../references/subagents.md), then select its `subagent_type` in a new non-fork context. Pass role, task paths, file boundaries and the waiting handshake; record the actual host identity and launch trace. Register it with `agent_selection`, then deliver the generated packet through the tool's supported messaging mechanism. Check actual file access and inherited project/user instructions.

For a selected native agent, omit a per-call model so its definition applies; for fallback, explicitly request the observed parent's model. Record environment or managed-policy substitutions and capability gaps. Retain native launch, command and result traces. Distinguish busy slots from an absent fresh-context mechanism or a lost agent. If the tool cannot demonstrate fresh context, use a clean CLI session only after runtime probes establish version, existing login, isolation and workspace access. Do not invent tool flags or report a simulated adapter test as native execution.

For a mode handoff, use a fresh context and transfer only saved state, common contracts and the newly selected flow. Preserve one orchestrator owner throughout the transfer.
