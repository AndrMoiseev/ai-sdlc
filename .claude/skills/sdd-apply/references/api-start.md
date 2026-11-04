# Start API

Read the [common API contract](api.md) and installed operation help before
constructing a request.

`validate` accepts `project_root`, optional `change` and `work_kind`, and
`instruction: {text, source}`. The critical dependency `sdd-shared` must be in
the sibling directory next to `sdd-apply`; a missing dependency stops execution.
Preserve the returned basis. Use the actual explicit execution instruction and its
message or saved source; plan approval alone is not an execution instruction.
Approval and permission to execute may appear in one message. Verify the instruction's
scope and latest cancellations or pauses before calling `initialize`; reuse existing
applicable permission without asking again. The API checks that instruction text and
source are present; the agent verifies that the user's words actually authorize execution.
Validation checks the single approval of the document bundle including its plan
through shared API v2 check/checkpoint interfaces, using the plan structural check.
Select an ambiguous change; return missing approval
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
does not authorize new tasks. Use `revised_plan` to reconcile changed scope while
preserving work. Its `instruction` records explicit permission to execute the revised
scope and its source. Revised plan approval alone does not grant that permission.
An existing instruction may be reused only while it still covers the revised scope
and has not been cancelled, replaced or paused.

`initialize` takes validation arguments plus optional `isolation`.
It validates, records a run and generates the
initial dashboard. Existing state requires [resume](../flows/resume.md).

Set `isolation: true` only after verifying task worktrees. Initialization stores the
execution instruction in `basis.instruction`; recording it does not create permission.
Revised plans replace the basis with the verified applicable execution instruction.
Unsupported legacy execution states are rejected without rewriting them.

For read/progress operations use installed help: `read`, `available`, `dashboard`,
`recover_lock`, `serve` and `stop_server` accept `directory`; `serve` also accepts
`port`, default 0. Follow [progress](progress.md) for dashboard lifecycle.
