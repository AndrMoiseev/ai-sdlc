# Start API

Read the [common API contract](api.md) and installed operation help before
constructing a request.

`validate` accepts `project_root`, optional `change`,
`instruction: {text, source}`, and optional `sdd_shared`. Legacy `sdd_spec` locates
sdd-shared alongside that path; supply only one explicit selector. Preserve the
returned basis. Validation checks both document and plan approval through shared
check/snapshot interfaces. Select an ambiguous change; return missing approval
or a missing plan to sdd-spec.

`initialize` takes validation arguments plus `owner`, optional `mode`,
`parallel_request` and `isolation`. It validates, records a run and generates the
initial dashboard. Existing state requires [resume](../flows/resume.md).

The default mode is `parallel`. Set `isolation: true` only after verifying it;
false falls back to `sequential` with `mode_reason: "isolation unavailable"`.
An explicit `mode: "sequential"` wins even when isolation exists. Parallel mode
stores a supplied `{text, source}` request or the execution instruction; it needs
no separate permission question. Resume and revised plans preserve saved mode;
a revised parallel run records the new execution instruction.

For read/progress operations use installed help: `read`, `available`, `dashboard`,
`recover_lock`, `serve` and `stop_server` accept `directory`; `serve` also accepts
`port`, default 0. Follow [progress](progress.md) for dashboard lifecycle.
