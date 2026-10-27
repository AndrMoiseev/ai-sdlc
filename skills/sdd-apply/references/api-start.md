# Start API

Read the [common API contract](api.md) and installed operation help before
constructing a request.

`validate` accepts `project_root`, optional `change`,
`instruction: {text, source}`, and optional `sdd_shared`. Legacy `sdd_spec` locates
sdd-shared alongside that path; supply only one explicit selector. Preserve the
returned basis. Use the actual plan approval text and its message or saved USER-record source as instruction; no additional execution question is needed. Honor explicit user restrictions on starting. Validation checks both document and plan approval through shared
API v2 check/checkpoint interfaces. Select an ambiguous change; return missing approval
or a missing plan to sdd-spec.

Admission requires `checkpoint_status.status: ready`. Input schema 2 stores
`plan_commit` and `document_paths`, without a normative byte manifest. Parsed
`document_records` preserve the admitted criteria and decisions for role packets.
Execution
naturally advances HEAD; ongoing transitions preserve the admitted task scope
and use independent source/candidate integrity checks. Checkpoint acceptance
does not authorize new tasks. Use `revised_plan` with an approved plan and an
explicit execution instruction to reconcile changed scope while preserving work.

`initialize` takes validation arguments plus `owner`, optional `mode`,
`parallel_request` and `isolation`. It validates, records a run and generates the
initial dashboard. Existing state requires [resume](../flows/resume.md).

The only supported `mode` value is `parallel`; callers may omit it. Set
`isolation: true` only after verifying task worktrees. Initialization stores a
supplied `{text, source}` request or the execution instruction; it needs no
separate permission question. Revised plans record the new execution instruction.
Unsupported legacy execution states are rejected without rewriting them.

For read/progress operations use installed help: `read`, `available`, `dashboard`,
`recover_lock`, `serve` and `stop_server` accept `directory`; `serve` also accepts
`port`, default 0. Follow [progress](progress.md) for dashboard lifecycle.
