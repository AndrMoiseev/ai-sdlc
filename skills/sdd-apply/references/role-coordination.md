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
checks, candidate reference, commits, blockers and rejected approaches. Send paths
and a bounded summary; exclude author conversation, grading answers and unrelated
task histories. Workers read their contract and task material, not execution algorithms.

Use actual fresh-context and messaging capabilities. Busy slots require waiting;
missing capabilities block the dependent launch. Reconcile a lost worker's actual
work before replacement through [resume](../flows/resume.md). Fabricated launch
attestations and test stubs never count as real independent work.
