# Codex adapter

Apply [role coordination](../references/role-coordination.md). Invocation or a verified sdd-spec plan-approval handoff is allowed by `agents/openai.yaml` with `allow_implicit_invocation: true`.

Discover the native tools actually exposed by this host. Resolve [project subagent selection](../references/subagents.md) before the waiting launch. Pass its `launch` parameters to `spawn_agent`, including `fork_turns="none"`, plus role, task paths, file boundaries and the waiting handshake. Record the returned identity and launch trace, register it with `agent_selection`, then deliver the generated packet using the host's messaging tool. The selected TOML supplies only model/effort; the role supplies instructions. Report unapplied definition fields.

Read results through native completion/messages and retain tool traces. Fresh conversation does not hide filesystem ancestors or the inherited skill catalog: inspect and report those limits. Use workspaces and host permissions for actual write boundaries. Do not claim `fork_turns="none"` alone provides filesystem isolation.

Distinguish unsupported launch tools, occupied slots, and terminated/lost agents. If native fresh contexts are unavailable, a clean CLI session is permitted only after runtime probes establish login, freshness and access. A prose reenactment of worker roles in the orchestrator is not a fallback.
