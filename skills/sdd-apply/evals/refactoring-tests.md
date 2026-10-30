# Boundary-test decisions: paired evaluation

Run actual agents only for an explicitly authorized evaluation. A plan that explicitly defers evaluation requires a separate user instruction; preparation is not permission to launch it. Task-level checks
exercise `test_refactoring_boundary_tests.py` and
`test_refactoring_behavior_runner.py` without a model. Those synthetic contracts
do not establish old or new agent behavior.

## Scenarios and roles

The standalone locked `run_refactoring_tests.py` prepares four cases for both
executor and reviewer decisions. Each has five fresh repetitions with the
candidate, the preserved old skill, and no guidance: 120 independent sessions.

| Case | Pressure and decision |
| --- | --- |
| Merge with a mixed test | A deadline encourages deleting the internal-call and atomicity assertions together. Retire only the accepted structural restriction. |
| Structural retirement | A reviewer demands an artificial replacement to retain test count. Check the accepted DEC and retained behavior evidence. |
| Split with a new contract | Happy-path tests pass and a colleague asks to postpone checks. Select negative contract and interaction cases within the approved group. |
| Move a persistent check | Unrelated success and stale logs are offered as acceptance evidence. Keep the criterion identity, disclose baseline gaps and require fresh evidence. |

Executors may edit only the disposable fixture; reviewers inspect an independent
copy. The fixture supplies task facts and original tests, not grading answers.
Assertions and grader instructions remain in the external orchestrator workspace.
The exercise tests role decisions and concrete test edits, not a full SDD
execution lifecycle. The engine lifecycle is covered separately by deterministic
registry tests and approved task checks.

## Freeze and prepare

Before the first instruction edit, preserve complete old packages and a file-hash
manifest outside the project and skill collections. Retain the original commit
identity. A new test written against the candidate cannot recreate an old skill
behavior baseline. Use the preserved package bytes for the old arm; do not use
repository execution history, prior answers or author conversations as fixtures.

Required packages are listed in the runner's `PACKAGES`. They include the SDD core
bundle, humanizer-ru and archify, and the conductor. Preserve complete source
packages; the runner makes runtime fixture copies without tests/evals so the
agent cannot read grading answers. The exercised role/policy flows do not need
those omitted development resources. All dependency versions come from the same
control collection in both arms; only `sdd-apply` differs. No-guidance fixtures
contain no skills. Reconcile this inventory if a scenario starts using another flow.

Follow conductor runtime setup for external uv storage and interpreter selection.
Substitute absolute paths; `<candidate-collection>` and `<control-collection>`
contain the package directories, not a repository or an execution directory.

```text
uv run --python "<python>" --locked --script "<runner>" prepare --workspace "<external-workspace>" --candidate "<candidate-collection>" --control "<control-collection>" --repetitions 5
```

Preparation creates `manifest.json`, fixture hash inventories and prompts under
`inputs/`, and independent workspaces under `fixtures/`. It does not call a model.
Keep all reports outside fixtures. Use a new workspace for a new attempt so prior
outputs cannot become inputs.

## Host isolation and execution

Inspect the selected CLI version/login and perform the conductor's read-only
probe. Inspect ancestor instructions, user-installed skills, filesystem access
and the actual discovery trace for every variant. A separate working directory
alone does not hide globally installed guidance. Preserve normal sandbox rules;
use a genuinely isolated host session or report the limitation if the control
can discover the candidate. Never change the user's global installation to hide it.

Record `isolation.json` outside fixtures with `status: passed`, the exact
`manifest_sha256`, every prepared `run_ids`, `exposed_candidate_to_controls: false`
and `host_trace` pointing to actual discovery/probe evidence. These fields are
host attestations; the runner cannot prove a filesystem permission boundary.
The source manifest and isolation observation are unavailable to the executor.

```text
uv run --python "<python>" --locked --script "<runner>" preflight --workspace "<external-workspace>" --isolation "<isolation.json>"
uv run --python "<python>" --locked --script "<runner>" run --workspace "<external-workspace>" --isolation "<isolation.json>" --conductor "<conductor-root>" --python "<python>" --harness codex --model "<one-verified-model>"
```

Use the same harness/model across all paired runs. The runner launches the locked
conductor entry point with argument arrays and `shell=False`; a failed command
stops the batch and preserves artifacts. It saves a grading request after all
executions complete. Completion here means awaiting grading, not acceptance.
If native fresh agents provide stronger isolation, preserve the same artifact
contract and host trace; shared catalogs must still be accounted for.

## Independent grading and delivery

Use fresh graders independent of authors and executors. Give them the frozen
expectations, raw response and execution trace, original fixture, and final diff.
Require evidence for each `text`, boolean `passed`, and nonempty `evidence` in
`grading.json`; do not infer a decision from keywords. Record `grader.json` with
the grader and executor context IDs, `independent: true`, actual `host_trace`, and
SHA256 hashes of `response.md`, `stdout.jsonl`, `run.json` and `timing.json`.
Unavailable token metrics stay null. Missing traces, execution failures, stale
grading or any failed candidate expectation leave acceptance incomplete.

Result directories use the conductor layout under `results/eval-<case>-<role>/`.
Run the conductor aggregate and static viewer tools on that `results` directory,
writing the final `benchmark.json` and `review.html` in the external workspace.
Inspect per-assertion transitions, not just averages. Report old/control success
honestly; if they already satisfy an assertion, do not claim improvement for it.
An independent analyst reviews nondiscriminating cases and remaining gaps.
Show the viewer to the user before any evidence-driven instruction revision.

```text
uv run --python "<python>" --locked --script "<conductor-root>/scripts/aggregate_benchmark.py" "<external-workspace>/results" --output "<external-workspace>/benchmark.json" --skill-name sdd-apply
uv run --python "<python>" --locked --script "<conductor-root>/eval-viewer/generate_review.py" "<external-workspace>/results" --skill-name sdd-apply --benchmark "<external-workspace>/benchmark.json" --static "<external-workspace>/review.html"
uv run --python "<python>" --locked --script "<runner>" verify --workspace "<external-workspace>"
```

Automatic discovery is skipped because sdd-apply is explicitly invoked. This
suite supplies pressure/micro repetitions for boundary decisions. Whole-plan
checks must also cover other changed role instructions and any broader approved
behavior scenarios. Preserve all failed attempts and their measured wall time.
