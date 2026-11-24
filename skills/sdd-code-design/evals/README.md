# sdd-code-design behavioral evaluations

The [scenario bank](evals.json) contains 64 tasks. The [coverage map](coverage.md)
links each source rule or practice to the exact expectation that assesses it.
Use the map to select cases for a chapter or a change. Entries in the map are
grader material.

## Focused diagnosis

Cases 1–3 in `evals.json` cover three read-only diagnoses: consumer obligations across an interface
change, a useful thin boundary, and a redundant forwarding chain. The TypeScript
files are synthetic source snapshots for diagnosis. Their `existingChecks` arrays
record baseline test expectations; they are not executable tests or evidence of a
successful test run.

Copy each case's source into a separate external workspace. Install the assigned
skill version with its `evals/` directory excluded so executors cannot discover the
grading criteria. Give them the task and source files; keep expectations, grading
and other runs' answers outside the executor workspace. Store execution traces and
results outside the skill package.

Compare old and new skill versions on the same cases and harness. For wording
checks, repeat the upload-interface case in five fresh contexts per version. Score
the architectural choice separately from explicit removal reasoning: an added
explanation does not establish that the previous recommendation was wrong.

## Comparing shared heuristics

Cases 4–8 are independent, read-only design and review tasks. Each has a synthetic
fixture, a task for the executor and four binary expectations for the grader.

| Case | Decision under test |
| --- | --- |
| 4 · billing-review | Which part of a review checklist can retire after adding a compiler check? |
| 5 · media-export | Who owns the position when a client resumes an export? |
| 6 · notebook-publish | Which operation must a test exercise, and how may it arrange the starting state? |
| 7 · usage-quote | What does an offline decoder check establish about a provider's response? |
| 8 · sample-release | Which alternatives, counts and ordering guarantees belong at each test level? |

For a paired comparison, copy the assigned runtime skill and just the case's
listed input file into each fresh workspace. Give both versions the same explicit
skill invocation and task. Keep the rubric, version labels and other responses
outside executor inputs. Fix the model, reasoning effort and repeat count before
starting. Score each answer against the four stored expectations and cite the
answer supporting each judgment. Record whether the executor reached the
relevant guidance separately from whether it made the right decision.

To examine the cursor example independently of how the skill routes case 5,
append the same instruction to both versions: read section 11 in
`references/decomposition/rules.md` before answering. Reuse the four criteria
and report this directed-reading comparison separately.

## Evaluating the rest of the skill

Cases 9–64 cover the chapter rules, guidelines and exceptions, agent-specific
guidance, and decisions in the patterns and workflows. Each asks for a decision
on concrete evidence. Some use two contrasting situations, such as a disposable
trial and a long-lived release, or a mixed-version fleet and a private function
with one caller. Score how the answer handles the condition that changes the
decision. Equivalent designs earn credit when they satisfy the stated criterion.

For an authorized run, give a fresh executor only the `prompt`, its assigned
runtime skill and the paths in `files`. An empty list means all the input is
in the prompt. Cases 32 and 46 have additional snapshots. Keep the catalogue,
coverage map, expectations and other answers outside that workspace. Grade every
expectation for the selected cases and cite the answer for each judgment.
Case numbers identify tasks; a reference such as `18.3` means the third
expectation of task 18, counting from one.

For version comparisons, keep the same prompts, snapshots, model, effort and
repeat count for both variants. Several source entries can point to one
expectation. Count that expectation once. State the denominator for each case
and report a directed-reading exercise separately from normal reference
selection. Cases 9–64 were authored as scenarios; the recorded Terra and Luna
comparisons concern cases 4–8.

## Design and SDD integration scenarios

These scenarios are prepared for a separately authorized behavioral evaluation;
they have not been executed by adding this procedure. Use fresh external fixtures,
keep grader expectations outside the worker context, and include complete sibling
`sdd-spec`, `sdd-apply` and their required dependencies for the SDD cases. Use their
normal packets and permissions. Record actual reads, writes, role results and
elapsed time; stop each scenario's process tree at 1200 seconds including setup.

| Scenario | Distinguishing observation |
| --- | --- |
| Outside-in design of order confirmation with requirements but no code or walking skeleton | Returns boundary examples, invariant owners, effect ordering and proposed checks; no implementation, test execution or claim of working software |
| Diagnose three design variants: confirmation before save; unspecified ordering; ordering specified with helper names left open. Requirement: a failed save sends no confirmation | Identifies a defect in the first, a material gap in the second and implementation freedom in the third; cites document evidence without requiring future code |
| Ordinary sdd-spec design and authorized review | Architect receives the explicit proposed-design outside-in call; each design reviewer receives focused diagnosis within its own lens. Results enter existing documents/FIND records; no extra role or review approval |
| Ordinary sdd-apply task with an approved contract | Executor receives outside-in implementation; code reviewer receives implemented-code diagnosis covering the owned diff. Verification retains behavior/test-sufficiency decisions; reviewers execute no checks; heuristic-only findings remain recommendations |
| SDD refactoring design, review and an authorized implementation task | Architect and executor receive the refactoring workflow with proposed design and implementation respectively; document and code reviewers receive diagnosis in their own lenses. Explicit calls and readable absolute paths reach each fresh context. Results use result/preservation and existing task/FIND records; verification and Explorer retain their own contracts |
| Design a publisher refactoring with proposal/design, original code and no specs; later review an early task contributing to the whole result | Produces the structural comparison and preservation sources without inventing REQ IDs or executing proposed checks. The code review assesses local acceptance at the current transition stage rather than demanding the final target in an early task |
| A preservation claim lacks baseline evidence; a new test passes on transformed code and has never run on the original | Names the gap and proposes characterization on the original implementation. Implementation obtains assigned evidence before dependent changes; the later green test is not reported as proof of prior behavior |
| A pure-calculation extraction materializes a stream before publication; publication failure must stop consumption | Traces the changed read/failure order to the preserved contract, proposes a discriminating failure case and retains effect ordering in the feasible transformation |
| Refactoring retires an internal call checked by both a structural test and a mixed atomicity test | The accepted structural retirement can remove its pure structural check. Behavioral assertions move to an appropriate boundary, with the approved test_changes and independently confirmed registry transition; verification owns sufficiency |
| An internal interface changes with its consumers; no compatibility adapter was authorized | The transformation updates the scoped consumers without adding an old API, dual path or adapter. A discovered conflict with required observable behavior returns to the caller before dependent work |
| Remove the required sibling entry point or selected workflow before a fresh ordinary-change or refactoring assignment | The orchestrator reports the specific dependency gap and does not claim that the dependent design, implementation or review completed |

For comparison, keep inputs, harness and model fixed across skill versions.
Judge concrete missed defects, unjustified findings, scope violations, document
and code quality, rework and total effort. More findings or a read of SKILL.md
alone do not establish improvement. Until an authorized run supplies evidence,
record the behavioral result as not run.

## Project heuristic scenarios

For an authorized behavioral run, prepare the project memory in the external
fixture using the [file contract](../references/project-heuristics.md). Keep the
grader's expected reads and writes outside that fixture.

| Situation and request | Distinguishing observation |
| --- | --- |
| Use the tenant-boundary fixture in a project with no local heuristics. The reviewer wants to remove a short wrapper and asks whether to record this as a lesson. | The agent defends the existing tenant and error guarantees from the code. The discussion can finish without a finding or a new memory file. |
| Supply a worker that retries a whole batch, a queue contract that redelivers that batch, and a trace showing repeated work. Ask for a lesson, then explicitly accept its wording and request the same save twice. | The agent compares whole-batch and item-level recovery, identifies a repeatable cue and a boundary, and distinguishes the trace from predicted costs. The first accepted rule creates one five-field inline entry. The repeated save leaves one entry. |
| Split accepted import and API-design entries for tasks that can select them independently. Then request an ordinary read-only review of the import worker. | The index points to complete, distinct groups. The reviewer reads the import group, applies its condition, skips the unrelated API group and returns its finding within the assigned scope. |
| Compare a local entry already covered by a bundled rule, a project-specific exception and a candidate for shared guidance. The candidate has been proposed upstream but is absent from the version used by the fixture. | The comparison identifies the covering section, preserves the local exception, explains the candidate's receiving context and limit, and keeps it locally available. Comparison alone produces proposals. |
