# Focused diagnosis evaluations

`evals.json` defines three read-only cases: consumer obligations across an interface
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
