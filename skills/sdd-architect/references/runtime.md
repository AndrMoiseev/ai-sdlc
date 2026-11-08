# Runtime and storage

Use `uv` and a system Python 3.11+; Git is needed only for history and revision
identity. JDK `jdeps` and `scc` are needed only for their selected collection
branches. detekt and JaCoCo tasks belong to the consuming project's build.
Missing a tool limits that branch; preserve the other available evidence.

## Report storage

Resolve `<project-root>` to the consuming project's absolute path. Before collecting
or drafting anything, create `<project-root>/docs/reports/{report-name}/` and use
that absolute path as `<report-dir>` throughout the run. Use the user's report name;
when none is given, choose a descriptive kebab-case name such as
`2026-11-08-pricing-audit`. Keep it a single directory component. If an unrelated
report already uses that name, choose an unused numeric suffix. Resume the same
report only when continuing that analysis; keep existing snapshots and use new
numbered outputs for further collection or comparison.

Keep all retained materials in `<report-dir>`:

| Material | Location relative to `<report-dir>` |
| --- | --- |
| Final report | `report.md` |
| Continuation state maintained by the orchestrator | `state.md` |
| Collection plan and captured identity | `collection-plan.md`, `identity-1.json` |
| Tool logs and generated input reports | `logs/`, `raw/` |
| Immutable snapshots and their raw input copies/configuration | `snapshot-1/`, `snapshot-2/`, ... |
| Calculated views | `analysis-1.json`, `analysis-2.json`, ... |
| Candidate shortlist and diagnosis index | `diagnosis.md` |
| Separate source diagnosis for each candidate group | `diagnoses/<group-id>/diagnosis-1.md`, `diagnosis-2.md`, ... |
| Saved assignment, actual launch and worker result | `assignments/<assignment-id>/request.json`, `launch.json`, `result.json` |
| Retained versions of mutable assignment inputs | `assignments/<assignment-id>/inputs/` |
| Authored cards, validated ordering and optional generated Markdown | `cards.json`, `ranked-1.json`, `ranked-1.md` |

Retain materials as they are produced, including incomplete results and collection
gaps. Direct report-producing tools here when supported; otherwise copy their
reports and logs here immediately, preserving original provenance. Existing inputs
may originate elsewhere; `collect` retains their raw copies in the snapshot.
Link retained evidence from `report.md` with relative paths so the report directory
can be reviewed as a unit. New outputs must resolve inside this directory, including
through symlinks. Do not overwrite an earlier run's artifacts.

Follow the [assignment and context contract](orchestration.md) for these records.
Keep [continuation state](continuation.md#save-continuation-state) linked to actual
requests, launches, results and primary artifacts; verify them when resuming.
The orchestrator writes requests, launch evidence and collection plans; the
assigned worker writes its result and named outputs. Keep assignment IDs and group
IDs stable, distinct and safe single directory components. Retain the input versions
behind a request before changing configuration, plans or cards. A completed group
diagnosis stays intact; a further diagnosis uses a new numbered output and the
index links the applicable result. Transfer an output only after the previous
writer's stopped state is verified. All retained audit records belong here;
caches and disposable execution state use external runtime storage below.

Maintain `<project-root>/.sdd/architect/collection.json` through
[Collection](collection.md#maintain-project-configuration). It is reusable project
configuration; each snapshot retains the configuration used for that collection.
For source-free work, use the destination project directory as `<project-root>`;
ask for it only when the working context provides none. Save the import configuration
as `<report-dir>/collection.json` and point its `repository` at `<project-root>`.

## Execution environment

Keep environments, caches, disposable fixtures and temporary build workspaces
outside the consuming project and all skill collections. Preserve inherited
`UV_CACHE_DIR` and `UV_TOOL_DIR`.
If absent, resolve the OS temporary directory through its API and set absolute
`uv-runtime/cache` and `uv-runtime/tools` paths for the current process. Create
them and check `uv cache dir` plus actual create/write/read/list access. Reapply
these variables and `PYTHONDONTWRITEBYTECODE=1` in new shells.

Find Python once: `uv python find --system --no-managed-python ">=3.11"`.
Use its absolute path in every run. Entry points have PEP 723 metadata and
adjacent lockfiles; no project environment or dependency setup is required.

```text
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" identity --config "<project-root>/.sdd/architect/collection.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" collect --config "<project-root>/.sdd/architect/collection.json" --output "<report-dir>/snapshot-1"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" analyze --snapshot "<report-dir>/snapshot-1/snapshot.json" --output "<report-dir>/analysis-1.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" rank --snapshot "<report-dir>/snapshot-1/snapshot.json" --recommendations "<report-dir>/cards.json" --output "<report-dir>/ranked-1.json" --markdown "<report-dir>/ranked-1.md"
```

Resolve placeholders before execution. Existing output paths are rejected to
retain the prior snapshot. JSON is the complete result; the Markdown output is
a starting report in the user's language, with at most five ready cards. Keep that
generated file separate from the integration architect's final `report.md`.
Inspect gaps in successful JSON results: success does not mean every measurement exists.

Register the resolved commands, cwd, exact input basis, outputs and limits in
`collection-plan.md` before assigning them to explorer. Register `identity` stdout
as a captured artifact such as `identity-1.json`; it has no `--output` option.
For `rank`, retain the exact completed cards version with the assignment and keep
it stable until the command returns. Further checks use unused numbered outputs;
link the relevant result from the authored report. The examples show command shape,
not permission for a research assignment to execute checks.

The scripts use only the standard library. Cached and empty-cache execution
therefore require no package download, including deliberate `--offline` runs.
Keep `--locked`; update a lock only as an intentional dependency change.

On filesystem errors, report the first failing path. Probe access with the same
interpreter and launch method; use the host's normal approval mechanism when
needed. Preserve the sandbox and ACLs. Windows commands launched by the collector
are hidden and terminate their process tree on timeout. It does not run arbitrary
command strings from a report or configuration.

Developer validation: run `scripts/test.py` through the same `uv --python ...
--locked --script ...` command. The full sequential suite has a 120-second
wall-clock budget including launch and setup. Stop the whole process tree if it
exceeds that budget. Keep evaluation results outside the package.
