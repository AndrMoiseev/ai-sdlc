# Role coordination

Read before launching workers. Resolve [project subagent selection](subagents.md)
for every new launch. Each task's executor starts fresh; verifier/reviewer contexts
are separate from every author. They may share one fresh context for that task
only when resolved launch identities match, with distinct role IDs and results.
Claude Code native-agent selections always use separate contexts. Final verifiers
start fresh. Repair may reuse a surviving executor with its existing selection;
a replacement requires a fresh successor registered through `successor_of`
and reconciled through `resume`.

The host adapter launches agents; scripts validate attestations and create packets.
Record observed context_id, launch_ref, raw launch/tool traces, selection and any
model/effort observations (unknown values are null). These strings do not prove
isolation cryptographically. Report inherited instructions, skills, filesystem
exposure and actual permissions; a read-only request is not a sandbox capability.

Launch in a waiting state with role identity and file boundaries. Register that
observed launch, then send the generated packet and role instructions. Reserve
`review_start` before substantive review. Keep role IDs active through their last
API operation. Collect results using the [worker contract](roles.md), including
separate verification/review results for a shared permitted context.

Packets identify task, original REQ/AC/design/instructions, files/interfaces,
checks, commits, blockers and rejected approaches. Send paths
and a bounded summary; exclude author conversation, grading answers and unrelated
task histories. Workers read their contract and task material, not execution algorithms.

Use actual fresh-context and messaging capabilities. Busy slots require waiting;
missing capabilities block the dependent launch. Reconcile a lost worker's actual
work before replacement through [resume](../flows/resume.md). Fabricated launch
attestations and test stubs never count as real independent work.

## Explorer dispatch

Before baseline, self, independent or integration, prepare a checks assignment
with the exact full registry IDs, registry revision and current basis. Use
`lib.explorer_assignments.basis(state, task, "checks", stage)` against the validated
saved state to construct the API basis; the engine recomputes it at registration
and execution. For null task final it uses the whole applicable final basis.
For research use `basis(state, task, "research")`, including null task scope;
research does not need a final registry. Preserve the shared assignment format
from [explorer](../../sdd-shared/references/explorer.md).

Launch the resolved `sdd-apply.explorer` in a waiting state, record the observed
capabilities under `capabilities.observations`, and register its `assignment`.
Use `role_id` as assignment `id`, the original project root as `scope.project`,
change ID as `scope.work`, and the task ID or null as `scope.task`. Pass the
resulting packet and [explorer instructions](../../sdd-shared/agents/explorer.md).
A continued context gets a new role ID after the prior role finishes; reuse only
within one task, with the same launch identity, outside final.

Stop writers and freeze the candidate before self/independent/integration.
Explorer requests the existing check API; the orchestrator may relay its request
with the real explorer trace. Return saved summary and raw artifact references
through the orchestrator to the independent verifier. The verifier reads needed
artifacts and test sources; it does not repeat deterministic execution. At final,
launch fresh separate explorer and final_verifier contexts for each applicable
scope. Keep behavioral/manual attestations with verifier/final_verifier.

For a task verifier, the generated packet's `verification` field supplies stage,
basis, applicable criteria and saved check-run/log/summary references. If that
verifier continues after another run, refresh these fields with
`lib.verification_results.packet(state, task, directory)` on the saved state and
send them through the orchestrator. Keep explorer conversation out of the packet.
The verifier reads raw artifacts through `read_object` and submits the separate
`verification_result` before finishing its role. Wait for both current execution
and conclusion to pass before review, transfer, commit or acceptance. After
integration, repeat the handoff for the integration basis.

For final_verifier, refresh with
`lib.verification_results.packet(state, task, directory, "final")`, using `None`
for a run-level scope. Obtain a separate final conclusion for every ordinary
task and, when registered, the additional project registry. Refactoring uses
the whole null scope. Send current evidence references after all procedures
have been aggregated; a newer attempt invalidates the previous conclusion.
Finish final_verifier only after `verification_result` is saved, then call
`finalize` and inspect execution evidence and conclusions separately.
