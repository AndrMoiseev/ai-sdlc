# Explorer assignments and capability evidence

Explorer is an SDD role for bounded research or checks. A host's built-in agent
named `explorer` does not establish its tools, permissions or launch capability.
Use [subagent selection](subagents.md) for profile resolution and actual launch
evidence, and give the worker [its role instructions](../agents/explorer.md).

## Before dependent work

Validate the saved assignment, then establish the host capabilities below within
the current permissions. Probe the actual runtime and allowed artifact directory;
a writable path in a different shell does not prove Python or child-process access.
Record each observation as `{available: true|false|null, trace, reason}`. `trace`
identifies the actual tool/catalog evidence or probe result; record a concrete
reason for unavailable or unknown capabilities.

| Capability | Required evidence |
|---|---|
| `launch` | Host can start the selected profile with the required context and instructions |
| `read` | Assigned sources can be read with the worker's tools and permissions |
| `write_artifacts` | Allowed outputs can be created, written, read and listed by the relevant runtime |
| `run_command` | Checks only: exact commands and required child processes can run under the current permissions |

`sdd_shared.explorer.validate_assignment(assignment)` validates the shared data
shape and raises `ValueError` on invalid input. `check_capabilities(assignment,
observations)` returns `ready`, `required` and `unavailable` records containing
capability, reason and trace. Both are data-only helpers: they neither probe the
host nor launch a role. A name, truthy string or unsupported assertion without a
trace cannot satisfy the gate. The caller checks the evidence against the actual
host and stops dependent work when `ready` is false. Preserve the limitation;
do not simulate the role or switch profiles to bypass a denied operation.

After launch, retain the actual host launch identity/trace and arguments alongside
the resolver selection. Requested model/effort and effective observations remain
distinct; unobserved values are null. A preflight observation is not proof that
the later launch succeeded. A failed launch stops the assignment.

## Assignment

Save these fields before dispatch; the calling workflow owns persistence:

| Field | Meaning |
|---|---|
| `id` | Stable assignment identity; apply uses role_id, spec uses the external request/result pair name |
| `kind` | `research` or `checks` |
| `scope` | `project`, `work`, `task` identities; each may be null before it exists |
| `basis` | Nonempty object identifying the actual source/documents/configuration basis |
| `read_scope` | Nonempty list of allowed source paths, object references or search bounds |
| `outputs` | Nonempty list of allowed artifact destinations; grants no source-edit authority |
| `limits` | Explicit time/output limits, including the whole-suite deadline where applicable |
| `question` | Research only: the bounded question |
| `check_ids` | Checks only: exact, unique registered check IDs |
| `stage`, `registry_revision` | Checks only: stage and nonnegative registry revision |

The consumer validates its concrete basis, registered commands, limits and allowed
destinations. The shared shape does not establish freshness, authorize a check or
create an execution state machine. Include the requested result form and ordinary
selection/launch evidence in the enclosing packet. Project research before a work
or task exists uses null scope values; it does not create a fictitious TASK.

For spec, save request/result/launch artifacts in a unique external directory under
the system temporary directory selected through the environment's API. Keep it
outside project, skill collections and uv cache. Save its absolute path and digest
in the continuation point. Missing answers remain unfinished; deleted artifacts
are unavailable evidence. Apply uses the existing role packets/results and store.

## Result and context

Return assignment ID, scope, kind, basis, status, selection/actual launch evidence,
capability limitations and artifact references. Research adds the answer, cited
sources, inspected scope, gaps, assumptions and questions. Checks adds the machine
summary/raw-artifact references and separate diagnosis. Keep full logs outside the
message; a verifier can inspect referenced evidence without rerunning a check.
Unknown counts remain null. Neither result type substitutes for a verification
result, approval or acceptance.

An explorer context stays separate from authors and substantive verifiers or
reviewers. The same task may reuse it for research, baseline, self, independent
and integration assignments with the same profile and a new current basis. Changed
inputs require new check evidence. Another task, a changed profile and final each
require a fresh explorer. Final also requires a separate fresh final_verifier.
The calling workflow enforces these boundaries and retains existing repair/retry
budgets; new assignments and contexts do not reset a whole-suite deadline.
