# Role coordination

Read before launching workers. Resolve [project subagent selection](subagents.md)
for every new launch. Each task's executor starts fresh. Each review lens uses
a separate fresh reviewer context, independent of every author and other lens,
even when all launches select the same model or native agent definition.
Repair may reuse a surviving executor with its existing selection;
a replacement requires a fresh successor registered through `successor_of`
and reconciled through `resume`.

The host adapter launches agents; scripts validate attestations and create packets.
Record observed context_id, launch_ref, raw launch/tool traces, selection and any
model/effort observations (unknown values are null). These strings do not prove
isolation cryptographically. Report inherited instructions, skills, filesystem
exposure and actual permissions; a read-only request is not a sandbox capability.

Launch in a waiting state with role identity, assigned lens and file boundaries.
After the full project checks pass, launch the required reviewers in parallel.
Register each observed launch with `kind: reviewer` and `lens_id: verification|code`,
reserve its `review_start`, then send the generated packet and lens instructions.
Both reservations belong to one round and the same frozen source/check run. Keep
role IDs active through their last API operation. Collect both results before
repair, extending checks or transfer. One passing lens cannot replace another.

Packets identify task, original REQ/AC/design/instructions, files/interfaces,
checks, commits, blockers and rejected approaches. Send paths
and a bounded summary; exclude author conversation, grading answers and unrelated
task histories. Workers read their contract and task material, not execution algorithms.

Use actual fresh-context and messaging capabilities. Busy slots require waiting;
missing capabilities block the dependent launch. Reconcile a lost worker's actual
work before replacement through [resume](../flows/resume.md). Fabricated launch
attestations and test stubs never count as real independent work.

## Explorer dispatch

Executor self-checks are local commands during implementation and repair. They
need no Explorer assignment or repair event and do not consume the failure budget.
The dispatch rules below govern registered Explorer checks.

Before registered baseline, self or independent checks, prepare a checks assignment
with the exact full registry IDs, registry revision and current basis. Use
`lib.explorer_assignments.basis(state, task, "checks", stage)` against the validated
saved state to construct the API basis; the engine recomputes it at registration
and execution. Null task scope is reserved for research.
For research use `basis(state, task, "research")`, including null task scope;
research does not need a check registry. Preserve the shared assignment format
from [explorer](../../sdd-shared/references/explorer.md).

Launch the resolved `sdd-apply.explorer` in a waiting state, record the observed
capabilities under `capabilities.observations`, and register its `assignment`.
Use `role_id` as assignment `id`, the original project root as `scope.project`,
change ID as `scope.work`, and the task ID or null as `scope.task`. Pass the
resulting packet and [explorer instructions](../../sdd-shared/agents/explorer.md).
A continued context gets a new role ID after the prior role finishes; reuse only
within one task, with the same launch identity, during task work.

After the executor reports completion, stop writers and freeze the candidate.
The orchestrator inventories project instructions, CI and configuration, registers
all required tests and static checks, and supplies their exact IDs and commands.
Explorer executes that complete assignment through the check API. It neither
selects checks nor judges sufficiency, acceptance, repairs or the next workflow
action. Return its machine summary and raw artifact references to the orchestrator.
Manual and behavioral checks are not supported by this task flow.

Only successful complete current execution permits reviewer launch. The verification
lens packet supplies stage, basis, applicable criteria and saved check-run/log/summary
references. It reads needed raw artifacts through `read_object` and submits the
separate `verification_result` within its reserved round, followed by `review_result`.
The code lens receives its own task packet without the verification reviewer's
conclusions. Keep Explorer conversation and all peer-review conclusions out of both
contexts. After a new run, launch fresh reviewers with current packets for both lenses.
Transfer requires current passed execution, criterion conclusion and both lens
verdicts. Commit and acceptance retain that worktree evidence without another handoff.
