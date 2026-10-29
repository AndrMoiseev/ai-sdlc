# Project subagent selection

Before each new role launch, resolve its selection from `<project-root>/.sdd/settings.json`.
Use the established project root, including when task code lives in a worktree.
The file selects agents; it does not authorize review, editorial work, parallel execution,
or new permissions. A configured model is already a project instruction: do not ask
again for permission to use it within authorized work.

## Roles and settings

| Role | Assignment |
|---|---|
| `sdd-spec.explorer` | Bounded source research and document/plan check execution |
| `sdd-apply.explorer` | Bounded source research and registered deterministic check execution |
| `sdd-spec.document_reviewer` | One fresh reviewer per document lens, including consistency and simplicity |
| `sdd-spec.plan_reviewer` | Separate fresh reviewers for plan and simplicity lenses |
| `sdd-spec.editor` | Authorized humanizer editing pass |
| `sdd-spec.editorial_reviewer` | Separate blind review of edited prose |
| `sdd-apply.executor` | Implementation, repair and conflict resolution |
| `sdd-apply.verifier` | Independent baseline, task and integration checks |
| `sdd-apply.reviewer` | Implementation review |
| `sdd-apply.final_verifier` | Fresh final checks at committed HEAD |

Use [settings.example.json](../templates/settings.example.json) as an optional template.
Version 1 maps role IDs to nonempty agent names under `subagents.roles`. Omit roles
that need no override. Multiple roles may select the same definition; this does not
authorize sharing their contexts. Version 1 has no lens-specific or per-task overrides.
Model IDs remain in native agent definitions, not settings.json.

Both explorer presets select one `sdd-explorer` profile with inherited model and
effort. Projects may select separate profiles for the two roles. Before dependent
work, follow the [explorer assignment and capability contract](explorer.md);
selection alone proves neither available tools nor an actual successful launch.

Missing settings, an unmapped role, or a missing selected agent uses the parent's
model. Report a missing named agent once per affected selection. Malformed settings,
unknown role IDs, duplicate JSON keys, invalid definitions or unsupported launch
parameters are errors, not reasons to silently choose another model. Preserve unrelated
top-level project settings. Do not create settings or agent definitions during normal use.

## Resolve before launch

Read the actual parent's model ID and, when exposed, reasoning effort from host metadata.
Do not guess them from an agent's answer or substitute a CLI's configured default.
If the host cannot reveal the parent model, use only a confirmed native inheritance
mechanism; otherwise record the capability gap and stop the dependent launch.

```text
uv run --locked --script "<shared-root>/scripts/resolve_agent.py" --project-root "<repo>" --role sdd-spec.document_reviewer --host codex --parent-model "<observed-model>" --parent-effort "<observed-effort>"
```

Follow [runtime setup](runtime-setup.md). The resolver only reads files and prints
`{ok, result}` JSON; it does not launch agents or write project settings. A nonzero exit
blocks that launch. Retain `result` before spawning. Recheck its source hashes immediately
before launch if preparation was interrupted. Resolve conflicting user instructions
before launch; never silently reinterpret an unavailable model as permission to fall back.

## Codex: model profile

Find the selected `name` in TOML files directly inside `.codex/agents/`, then
`$CODEX_HOME/agents/` (default `~/.codex/agents/`). A project match wins. Duplicate names
within the selected scope and malformed scanned TOML are errors. `--user-agent-dir`
is an explicit alternate user catalog, useful for isolated tests; do not invent one
to avoid a real project's settings. Identity comes from `name`, not the filename.

Use the resolver's `launch` fields as actual native `spawn_agent` arguments, together
with task name and role assignment. Keep `fork_turns: none`. `task_name` is not a
native agent selector. Translate `model_reasoning_effort` to `reasoning_effort`.
When the definition omits `model` or uses `inherit`, pass the observed parent model.
An omitted effort inherits the known parent effort for the same model; for a different
model leave it out to request that model's native default. Check the exposed API's
supported model/effort combinations before launch; the resolver has no fixed model catalog.

This adapter imports only model and effort. Keep the role's SDD instructions as the
assignment; do not import `developer_instructions`, tools, skills, permissions, hooks,
or other TOML fields. Report the resolver's ignored fields as unapplied profile settings.
Do not claim a complete native custom-agent launch or tool restriction. If the user
requires those additional settings, report the unsupported capability before proceeding.

## Claude Code: native agent

Obtain the available agent names from the actual Agent tool/catalog, including managed,
session and plugin agents. Save that array to an external runtime JSON file and add
`--host claude-code --available-agents "<catalog.json>"` to the resolver command
(replace `--host codex`). Do not infer availability solely from Markdown files.
Definitions normally live in `.claude/agents/` or `~/.claude/agents/`; let Claude Code
resolve their precedence and apply their model, system instructions and tool restrictions.

For `mode: native-agent`, pass the returned `subagent_type` and the SDD assignment to
the Agent tool. Omit a per-call model so the definition controls it. Start a fresh,
non-fork agent. Check that its instructions and tools can satisfy the assigned contract;
a read-only reviewer definition cannot serve as an executor.

For `mode: parent`, use the available `general-purpose` agent and explicitly request
the parent's exact model through the supported invocation parameter. If that fallback
type or model parameter is unavailable, report a capability gap. A denied agent or
failed launch is not a missing definition: preserve the failure rather than bypassing it.
Environment overrides such as `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and managed policies
may prevent the requested model. Record the actual substitution or limitation; never
silently alter global settings. A definition without `model` follows native Claude Code
defaults; use `model: inherit` in the definition when parent inheritance is intended.

## Evidence and continuation

Record the resolver result, actual launch arguments, launch identity/trace and any
runtime-reported model/effort. Requested parameters are not proof of the effective model;
use `null` for unobserved values. Keep this evidence with the review run or editorial
checkpoint. For sdd-apply, retain it as `agent_selection` in `role_register`; retain
observations separately as `model_observation` with their source trace.

Keep a running agent's selection fixed, including executor repair and resume. A new
selection applies to a new launch; changing an existing executor requires a fresh
successor and handoff. Settings changes are included in the repository-wide Git checkpoint review.
In sdd-apply, tracked/nonignored configuration files participate in ordinary source
snapshots: edits can invalidate candidate checks or violate task scope. Change selection
between tasks or reconcile it through the existing recovery/check procedure; do not
exclude configuration from source checks to bypass those protections.
A new review still follows existing consent rules.
Verifier and reviewer may share a context only when their resolved launch identities
match and the original independence rules permit it; otherwise use separate fresh agents.
For Claude Code custom agents, always use separate verifier/reviewer contexts: the
catalog names alone do not prove that the native definition stayed unchanged.
Refresh the actual Claude catalog immediately before launch. Re-resolution in scripts
checks Codex definition precedence and missing-agent recovery; it cannot query a live
Claude host or prove that an attested catalog is current.
