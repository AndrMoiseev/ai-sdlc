---
name: sdd-implement
description: Execute or resume a ready OpenSpec change from an existing specification and plan on explicit user invocation. Does not draft requirements or publish changes.
disable-model-invocation: true
---

# SDD Implement

Execute the selected ready change through implementation, automatic checks, task review, and a final independent review. Preserve requirements; resolve technical details autonomously. The coordinator owns sequencing, Git commits, and durable progress. Use the user's language for updates and reports.

Invoke explicitly with `$sdd-implement` in Codex or `/sdd-implement` in Claude Code. After invocation, execute the workflow autonomously within its existing boundaries.

When the current agent is neither Codex nor Claude Code, or its host is unknown, use the [arbitrary agent adapter](references/generic.md). An explicit request to use `sdd-implement` is sufficient invocation in that branch.

## Roles and prerequisites

| Role | Model | Reasoning |
| --- | --- | --- |
| Task implementer | `gpt-5.6-terra` | `high` |
| Task reviewer | `gpt-5.6-sol` | `xhigh` |
| Codebase researcher | `gpt-5.6-luna` | `medium` |
| Final reviewer | `gpt-6-astra` | `high` |

These are defaults; honor explicit user overrides and persist them. The coordinator keeps its current model. Pass the exact model and reasoning to the agent tool. With `collaboration.spawn_agent`, use `fork_turns: "none"` and a self-contained assignment when overriding models; full-history forks cannot set these overrides. Other runtimes must expose equivalent controls. If the required model, reasoning, or delegation capability is unavailable, report the limitation and ask for a substitution; do not silently fall back.

Each task gets a fresh implementer and a separate fresh reviewer. Reuse that pair for the task's correction cycles. Launch the next implementation only after this task's review disposition, or after parking a task blocked on external input. Never implement two tasks concurrently. Implementers and reviewers may delegate bounded, read-only codebase research using the researcher settings. Researchers do not implement, commit, or recursively delegate. End completed agents when supported to leave capacity for the next pair and research.

Before dispatching agents, read [Agent assignments](references/agents.md). Before creating or restoring progress, read [Progress and manual checks](references/progress.md).

## 1. Establish the change and baseline

Use the change named by the user or unambiguously identified in the conversation. Otherwise list active changes with `openspec list --json`; select the sole candidate or ask the user to choose. Identify the implementation repository and the authoritative planning root separately: they may live in different repositories.

If a registered store is selected, discover its identifier using `openspec store list --json` and retain `--store <id>` on every supported change/context command. Use installed CLI help when command support or returned fields differ. Run:

```text
openspec status --change <name> --json
openspec instructions apply --change <name> --json
```

Use returned paths, schema, tasks, and context files; do not assume `openspec/changes` or fixed artifact names. Read all listed context files and applicable `AGENTS.md` instructions, including nested instructions for touched files. Apply required project context and compatible operation guidance. Keep advisory guidance separate from authoritative state and evidence. Respect edit constraints and a CLI `blocked` state; explain missing artifacts instead of bypassing it. Use this skill's execution loop directly, without invoking another apply skill that imposes a conflicting stop/review policy.

Inspect the Git branch, HEAD, working tree, index, and relevant existing implementation. Record a fixed baseline and existing user changes before any edits. Preserve unrelated changes and staged entries. Commit only attributable task changes; isolate hunks or ask about overlapping edits when attribution cannot be established. Avoid changing branches or rewriting history merely to run the workflow.

Derive automatic checks from project instructions, CI, the plan, and affected behavior. Record commands, working directories, and applicability. Required automatic checks must pass before each implementation or correction commit. A required check that cannot run is a blocker; do not relabel it as manual merely to continue. No project-specific language, OS, build command, or test framework is hardcoded by this skill.

Before assigning test work or running checks, read [Test scope and execution budgets](references/testing.md). Include that policy and concrete check deadlines in implementer assignments. Use minimal behavior-focused fixtures for routine regression coverage. Adding, expanding, or separately running load/stress tests or performance benchmarks requires an explicit user request; general quality requirements and reviewer suggestions are insufficient.

Restore existing progress against Git, artifacts, and current code. CLI `all_done` or checked tasks alone do not prove review completion: finish missing reviews and final validation for already implemented work. Announce the selected change, baseline, progress, and next task.

## 2. Execute one task

Choose the next pending task in plan order whose dependencies are satisfied. Clarify implementation steps within existing requirements when needed and record the reason. Changes to requirements, acceptance criteria, scope, or a binding design decision require user input. Never narrow behavior or weaken a check to make a task pass.

1. Record the task's starting commit and acceptance criteria. Dispatch its implementer with the specification, plan, constraints, check commands, and task boundary. The implementer changes code, adds meaningful tests where needed, and prepares manual test cases for behavior that needs human verification.
2. Obtain implementation evidence and run or verify every applicable automatic check on the exact candidate tree. Fix failures while an evidence-based next step exists. If the candidate changes after validation, rerun affected checks and any checks required on every candidate by project rules. Inspect the staged diff and preserve unrelated staged work.
3. Once the specified implementation and automatic checks are complete, mark the implementation task complete in the plan and record `awaiting_review` separately. If the task is explicitly a manual execution task, retain its unchecked/pending status until a human actually runs it; this status does not block subsequent implementation tasks. Commit the task before launching its reviewer. Use repository commit conventions and include the change/task identifier. Record the resulting hash. Never claim a commit succeeded without verifying it.
4. Dispatch the independent task reviewer against the task base and committed HEAD, including relevant surrounding code and specification. Record all findings with severity, evidence, and disposition. Review covers both specification conformance and mandatory repository standards, plus correctness, regressions, and security.
5. Send only critical findings, as defined below, to the same implementer for correction. Save all other findings in the technical-debt journal without dispatching fixes for them. For each correction cycle: implement fixes, pass applicable automatic checks, create a separate correction commit, then request another review from the same reviewer. Do not amend or squash the implementation or prior correction commits. Save the correction commit and pending cycle number before requesting rereview; increment and save the completed cycle count only after that rereview returns.
6. Allow at most three correction cycles after the initial review. After the third correction commit, the reviewer checks the result. If critical findings remain, stop the entire run and report them. A review with no critical findings finishes the task immediately, including when technical debt remains; proceed to the next task without spending correction cycles on debt. Do not produce empty commits for a clean review or a discussion that changed no files.

### Review threshold

Use the same threshold for task review, rereview, and final review. A finding is **critical** only when evidence demonstrates either:

- A direct contradiction of an explicit requirement or acceptance criterion in the approved specification, interpreted together with its operating assumptions, design constraints, and stated exclusions. Cite the requirement and the actual conflicting behavior within that supported scope; a reviewer's preferred design is not a requirement. A rare case qualifies through this route only when the specification explicitly requires that case or guarantee.
- A serious implementation error with a high likelihood of failure in typical supported use. Show the ordinary trigger, reachable code path, and concrete consequence, such as broken core behavior, data loss, or an exploitable security failure. Support the likelihood with code, tests, or actual usage constraints.

All other findings are **technical debt**, including speculative or unlikely corner cases outside explicit requirements, optional hardening, minor defects, and maintainability or style suggestions. Severity labels and a merely possible failure do not establish criticality. Resolve classification from the specification and evidence; concerns that do not meet the threshold remain potential problems in the journal, with uncertainty stated. Promote a deferred finding only when new evidence satisfies the threshold. A genuine ambiguity in requirements follows the existing requirement-blocker procedure.

For concurrency and timing findings, identify who changes state, whether that activity is expected during the operation, and the necessary interleaving. A general requirement such as detecting external changes does not by itself promise an atomic snapshot, continuous monitoring, or protection against every concurrent writer. A deterministic test that injects a write at an internal hook proves possibility, not typical-use likelihood or an explicit contract. For example, a file changing after the last content read during snapshot capture is technical debt when editing is expected only on pause and atomic capture is not required, unless evidence establishes a serious failure highly likely in supported use. Repeating a read merely moves the final observation boundary; assess a proposed fix against the actual required guarantee.

Mandatory project instructions and required automatic checks remain execution gates; this review threshold does not authorize bypassing them or weakening the specification. Persist technical debt using [Progress and manual checks](references/progress.md).

The three-cycle limit counts completed correction-and-rereview cycles, not individual debugging attempts. An inability to produce a passing correction candidate is a blocker; do not create a failing commit to consume a cycle. Keep the implementation checkbox and review status distinct; reopen a checkbox when a confirmed critical finding invalidates the claimed implementation.

## 3. Handle blockers and human checks

For an ordinary blocker, save evidence, unfinished work, dependency impact, and the concrete question or missing resource. Continue independent unblocked tasks sequentially when their changes and checks can be isolated safely. If the current uncommitted edits cannot be separated, pause instead of mixing tasks. Do not silently stash, discard, or commit failed work. A requirement decision may remain pending while independent work proceeds.

Correct implementation and check failures autonomously while new evidence supports the next attempt. Stop repeating an identical failed approach when no useful next step exists. Missing permissions or external resources require a concrete request. Critical findings after three correction cycles and critical final-review findings are global stops, not opportunities to skip to another task.

Human checks do not block commits or further execution. For every necessary human check, write prerequisites, exact actions, expected results, and the linked task directly in that task's plan entry. Consolidate these into a change-level manual test plan by the end, linking back to the tasks. Reuse an existing suitable manual plan when present. Keep execution status `not run` until actual evidence is provided; a written plan is not a passed test. Work requiring human execution remains explicitly pending even when autonomous implementation is finished.

For a task consisting entirely of human execution, use its implementer/reviewer pair to prepare and review the manual instructions and any autonomous setup. Apply the normal checks/commit/review loop to attributable preparation changes in the implementation repository. If there are no such changes (for example, instructions already exist or only separate-store planning records changed), skip the empty implementation commit and have the reviewer inspect the saved instructions directly. Record preparation review separately from pending human execution, then continue. This exception does not permit skipping commits or checks for code changes. A dependency on human execution alone is deferred with that execution; a genuine missing implementation prerequisite still blocks dependent work.

## 4. Validate the whole change and run final review

After every implementable task has a review disposition and ordinary blockers are resolved, verify the combined result against the full specification and run the required whole-project automatic checks. Verify manual cases have been consolidated and every task, finding, and deferred human step is accounted for in progress or its linked journals. Fix automatic-check failures through the responsible task's implementer, checks, separate correction commit, and task reviewer; preserve its cycle count. If that task has exhausted its correction allowance, stop and report the failure. Do not start final review on a failed automatic candidate.

Launch a fresh final reviewer with the final-review model and reasoning. Give it the original fixed baseline, current committed HEAD, full change artifacts, all task review dispositions, known unresolved findings, check evidence, and the manual test plan. The review covers the entire change and interactions across tasks. Review any relevant uncommitted planning records separately from the committed implementation.

Apply the review threshold to every final finding, including previously deferred debt. Save non-critical findings in the technical-debt journal; they do not prevent completion. **If final review reports a critical finding, save it and stop. Do not dispatch fixes, create a correction commit, modify requirements, or begin another review cycle automatically.** Report critical findings with severity, evidence, affected tasks, and what requires user direction. Pending manual execution alone is a disclosed status, not automatically a code finding. A missing or unusable required manual plan can be a finding.

If final review has no critical findings, record autonomous completion, with manual execution still pending when applicable. Report implemented tasks, implementation/correction commits, automatic-check results, and the manual plan location. Present technical debt only as a link to its journal and the number of distinct open potential problems, without listing or summarizing them in the user-facing report. If there is no debt, report zero without creating an empty journal. Distinguish saved local progress files from committed changes. Never claim full verification while human checks remain unexecuted.

Push, PR creation, merge, deployment, spec synchronization, and archiving require a separate user instruction. This workflow authorizes its local task and correction commits only; it does not authorize external publication.
