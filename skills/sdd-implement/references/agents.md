# Agent assignments

The role/model table in `SKILL.md` is authoritative. Supply exact model and reasoning at dispatch, including for researcher children. Keep assignments self-contained so fresh agents do not depend on inherited conversation. Agents share a filesystem unless the runtime explicitly provides isolation.

## Implementer

Provide repository and planning-root paths, change/task identity, specification and design paths, precise task text, task base commit, dependencies, applicable project rules, automatic checks, existing user edits, and permitted files/scope. Tell the agent:

- Implement only this task, taking technical decisions within the approved requirements.
- Follow the supplied test policy from `references/testing.md`: tie new tests to requirements or demonstrated regressions, use minimal sufficient fixtures, and measure new tests individually before running the full suite. Adding, expanding, or separately running load/stress tests or benchmarks requires an explicit user request.
- Run applicable checks within the supplied deadlines and provide command, working directory, elapsed time, result, and relevant failure evidence. On timeout, stop the owned check processes and report diagnostics rather than continuing to wait.
- Describe files changed, acceptance-criteria coverage, assumptions, and human checks with steps and expected outcomes.
- Report a requirement conflict or unavailable dependency without weakening the task.
- Leave Git commits, task status, and shared progress bookkeeping to the coordinator.
- You may delegate bounded read-only codebase research using the researcher model/reasoning from the supplied role table. Research children must not modify files or spawn children.

For fixes, send only critical finding IDs, evidence, cycle number, and current commit back to the same implementer, together with the review threshold from `SKILL.md`. Request a finding-by-finding disposition. Keep deferred technical debt outside the correction scope. Preserve the task boundary; report any fix requiring new requirements.

## Task reviewer

Provide task text, specification/design paths, repository rules, task base and candidate commits, implementation scope, check evidence, human-check cases, and known user edits. Request a read-only review. The reviewer's independent judgment is based on the specification and code, not the implementer's assertion of success.

Include the review threshold from `SKILL.md` in the assignment. Check specification conformance, mandatory standards, correctness, regressions, security, acceptance coverage, and whether tests meaningfully cover affected behavior. Focus investigation on explicit requirements and typical supported scenarios. Each finding needs a stable ID, severity, critical/technical-debt classification with rationale, a concrete file/location, evidence or reproduction, impact, and suggested correction. Critical findings must cite the violated requirement with its relevant operating assumptions and exclusions, or demonstrate a serious failure highly likely in typical use. Apply the concurrency guidance in the threshold to timing-dependent findings; distinguish a reproducible injected interleaving from evidence of expected use. For debt, state any assumptions or uncertainty. Return critical findings and technical debt separately, explicitly stating when there are no critical findings. Recommendations must identify a concrete benefit; avoid stylistic churn without a project rule or observable concern.

The reviewer may run non-mutating checks and use the researcher role for read-only codebase investigation. It must not fix code, commit, mark tasks complete, or invoke another review skill that expands delegation beyond the agreed roles.

Apply `references/testing.md` to test recommendations and new test code. Assess whether fixture scale is necessary for the asserted functional behavior. Treat unrequested load/stress coverage and benchmarks as potential technical debt, not correction requests; reviewer recommendations cannot authorize that testing. Classify findings using the same review threshold as production-code findings.

On rereview, supply the original task base, new candidate, prior findings and correction commit. Verify fixes and check for regressions introduced by them. Retain finding IDs and distinguish resolved, remaining, and new issues. Review the complete task result, not only the last patch.

## Final reviewer

Use a fresh agent with the final-review configuration. Provide full requirements and plan, original baseline, committed candidate HEAD, applicable rules, relevant planning records, task review history, automatic-check evidence, technical-debt journal, manual plan, and the review threshold from `SKILL.md`. Request a read-only review of combined behavior, integration between tasks, omitted requirements, regressions, mandatory standards, and verification gaps.

Use the same evidence-based finding format and threshold as task review. Reassess deferred findings against the combined result, retaining their IDs; promote debt only with new evidence satisfying the critical threshold. Distinguish pending human execution from missing implementation or missing test instructions. The final reviewer reports only; critical findings cause the coordinator to stop without automatic fixes, while technical debt is journaled and permits completion.

## Researcher

Give one bounded codebase question, relevant paths, and the caller's needed decision. Request file/line evidence and a concise answer. Use the researcher configuration from `SKILL.md`. Read-only; no implementation, Git mutations, or further delegation.

## Agent lifetime

Reuse each task's implementer and reviewer across that task's cycles while available. If context/session loss makes them unavailable, recreate only the missing role with its original settings and full saved task history; record the replacement. Do not pretend an old agent session survived. Await or stop all outstanding task research before accepting the task disposition and advancing to the next implementation. Respect runtime concurrency capacity; research can wait for a slot without changing model or starting parallel implementation.
