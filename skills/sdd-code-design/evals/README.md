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
