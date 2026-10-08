# Codex adapter

Apply [role contract](../references/roles.md). Explicit invocation is enforced by `agents/openai.yaml` with `allow_implicit_invocation: false`.

Discover the native tools actually exposed by this host. For native collaboration, launch with `spawn_agent` and `fork_turns="none"`; pass only role, task paths, file boundaries and the waiting handshake. Record the returned identity and launch trace, register it, then deliver the generated packet using the host's messaging tool. Use the session's model unless the user authorized a different one.

Read results through native completion/messages and retain tool traces. Fresh conversation does not hide filesystem ancestors or the inherited skill catalog: inspect and report those limits. Use workspaces and host permissions for actual write boundaries. Do not claim `fork_turns="none"` alone provides filesystem isolation.

Distinguish unsupported launch tools, occupied slots, and terminated/lost agents. If native fresh contexts are unavailable, a clean CLI session is permitted only after runtime probes establish login, freshness and access. A prose reenactment of three roles in the orchestrator is not a fallback. Transfer mode changes to a new owner context without forwarding the previous mode's conversation.
