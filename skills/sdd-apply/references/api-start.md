# Start API

Read the [common API contract](api.md) and installed operation help before
constructing a request.

`validate` accepts `project_root`, optional `change` and `work_kind`, and
`instruction: {text, source}`. The critical dependency `sdd-shared` must be in
the sibling directory next to `sdd-apply`; a missing dependency stops execution.
Preserve the
returned basis. Use the actual plan approval text and its message or saved USER-record source as instruction; no additional execution question is needed. Honor explicit user restrictions on starting. Validation checks both document and plan approval through shared
API v2 check/checkpoint interfaces. Select an ambiguous change; return missing approval
or a missing plan to sdd-spec.

Admission requires `checkpoint_status.status: ready`. Check reports are consumed
during validation and are not included in the returned or saved basis. Admission
requires a clean working tree; the empty `dirty_paths` list is not saved in basis.
Input schema 2 stores
the admission `head`, without a document inventory, normative byte manifest or
copy of parsed documents. Document names are derived from the fixed plan filenames
and, for changes, `specs/**/spec.md` tracked at the main repository's `HEAD`.
Runtime consumers read required records from `HEAD` of
`basis.project_root` through the repository adapter and the sdd-shared Markdown/YAML
parser. Role packets provide document paths and that original project root;
task worktree HEADs and uncommitted edits are not document inputs.
Execution
naturally advances HEAD; ongoing transitions preserve the admitted task scope
and use current Git state checks. Checkpoint acceptance
does not authorize new tasks. Use `revised_plan` with an approved plan and an
explicit execution instruction to reconcile changed scope while preserving work.

`initialize` takes validation arguments plus optional `isolation`.
It validates, records a run and generates the
initial dashboard. Existing state requires [resume](../flows/resume.md).

Set `isolation: true` only after verifying task worktrees. Initialization stores the
execution instruction in `basis.instruction`; it needs no separate permission
question. Revised plans replace the basis with the new execution instruction.
Unsupported legacy execution states are rejected without rewriting them.

For read/progress operations use installed help: `read`, `available`, `dashboard`,
`recover_lock`, `serve` and `stop_server` accept `directory`; `serve` also accepts
`port`, default 0. Follow [progress](progress.md) for dashboard lifecycle.
