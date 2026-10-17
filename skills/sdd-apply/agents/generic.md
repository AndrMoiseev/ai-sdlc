# Arbitrary agent adapter

Read [project subagent selection](../references/subagents.md) when settings exist.
The shared resolver supports Codex and Claude Code only. Preserve configured overrides
and report an unsupported host before dependent launches; do not label another host as
Codex to satisfy registration. Without overrides, use only confirmed host inheritance.

Use this adapter when the current agent is neither Codex nor Claude Code, or its host is unknown. An explicit request to use `sdd-apply` starts the workflow; no slash command, installation directory, or metadata enforcement is assumed.

Follow the API and role contracts using only capabilities exposed by the current environment. Establish access to project files, command execution, durable state, fresh contexts, role messaging, and launch evidence before the steps that need them. An installed CLI does not identify the current host.

Describe each assignment in prose: role, task, source material, permitted changes, required checks, and expected evidence. A fresh worker receives only that assignment and its sources, without the author's conversation. For each role, obtain the actual identity and launch evidence, register the waiting worker, then deliver the generated packet. Reserve review before substantive review starts. Preserve the sequence in [roles](../references/roles.md); prose instructions do not implement missing host operations.

Use confirmed permission and workspace controls; distinguish requested read-only behavior from enforced isolation. If fresh contexts, messaging, attestations, commands, or persistence needed by the API are unavailable, report the specific gap and leave dependent execution blocked. Continue independent preparation only. Do not invent role IDs, successful checks, commits, or saved state. A self-review cannot satisfy an independent review. Apply the existing sequential fallback when parallel isolation is unavailable.
