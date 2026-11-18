# Runtime and storage

Use `uv` and a system Python 3.11+. Full audits require Git, jdeps, scc, JDK 17+,
an existing detekt runtime, the bundled measurement plugin and complete detekt/JaCoCo reports.
Gradle build/test/report tasks belong to the consuming project. Missing tools or
mandatory sources block a full audit. Explicit focused routes can use partial inputs.

## Report storage

Before producing materials, establish
`<project-root>/memory/tech-debt/audits/<date-time>/` and use its absolute path as
`<report-dir>`. Use a UTC start timestamp `YYYY-MM-DDTHH-mm-ssZ`, for example
`2026-11-14T14-30-00Z`. For a collision use fractional seconds before `Z` (up to
six digits) and create an unused directory. Keep a descriptive audit title inside
the report. Resume an unfinished audit in its existing directory. Retain completed
audit materials; later investigations use a new timestamp and link their predecessors.

The current plan is separate: `memory/tech-debt/plan/plan.md` and
`memory/tech-debt/plan/tasks/<task-name>/task.md`. Follow
[plan maintenance](tech-debt-plan.md) for automatic additions and user changes.
Measurement and ranking commands write only inside audit directories.
After the complete full audit succeeds, the final `status` command alone replaces
`memory/tech-debt/status.json`, `status.md` and `status-indicators.md` under the
[publication contract](quality-indicators.md#publication).

| Material | Location relative to `<report-dir>` |
| --- | --- |
| Final report and continuation state | `report.md`, `state.json` |
| Audit configuration and collection plan | `collection-input.json`, `collection-plan.md` |
| One retained copy of each raw input and tool logs | `raw/`, `logs/` |
| Collection parameters, output links and outcomes; no value tables | `collection.json` |
| Effective numerical policy | `collection.json.analysis_policy`, read through `metrics.py policy --collection` |
| Calculated project/module aggregates, awaiting final publication | `metrics/quality-indicators.json` |
| One metric at one granularity | `metrics/<metric>/<granularity>.jsonl` |
| Keyed sorting and threshold selections | `selections/rankings.jsonl`, `selections/signals.jsonl` |
| Preliminary groups with overlaps and complete investigation queue | `selections/candidate-groups.jsonl`, `selections/investigation-queue.jsonl` |
| Candidate shortlist and diagnosis index | `diagnosis.md` |
| Separate bounded diagnoses | `diagnoses/<group-id>/diagnosis-<n>.md` |
| Saved assignment, launch and worker result | `assignments/<assignment-id>/request.json`, `launch.json`, `result.json` |
| Six-section Markdown recommendation cards | `recommendations/<id>.md` |
| Compact ranking metadata, validated ordering and optional rendered table | `cards.json`, `ranked-<n>.json`, `ranked-<n>.md` |

Source paths are relative to the project with `/`. Markdown links are relative to
the containing document; measurement addresses are relative to the report directory,
and the metadata's `card` path is relative to `cards.json`. Resolve writes inside the intended report,
including symlinks. `collect --output` accepts the report directory itself, including
pre-existing `raw/` and plans, but rejects an existing `collection.json`, `metrics/`
or `selections/`. Further collection uses a new timestamped audit directory, linked from
the audit being continued. Do so only for a measurement need, never a version check.

The aggregate document is separate from keyed JSONL diagnostics. Do not copy source trees.
Keep each audit's input in `collection-input.json` beside its output `collection.json`,
which records used measurement parameters and resolved [analysis policy](analysis-policy.md).
All paths in input configuration are project-relative with `/`, including report
paths and command arguments. Pass the project root as runtime `--repository` for
`configure`, `collect`, `rank` and `status`; cwd and the input file's location do
not define the path base. External tool locations stay in runtime arguments.
Project numerical overrides in `.sdd/architect/analysis-policy.json` are read-only;
changing project settings belongs to user-initiated `sdd-setup`. Copy external
reports once into `raw/` before saving their project-relative input paths;
the collector reuses inputs already there.

Retain partial outputs and concrete gaps. The collection description starts with
`status: incomplete` and every planned output marked incomplete. Normal completion
accounts for each output as `complete`, `unavailable` or `error`; an interrupted
calculation remains distinguishable from a successful empty JSONL file. Outcome
metadata, parameters and gaps stay outside metric rows.
In a full audit, a required source failure sets collection `status: blocked` and
raises an actionable error. No live status file is touched. Independent partial
chains are allowed only for explicitly focused work.

Use the [assignment contract](orchestration.md) for roles and output ownership.
The orchestrator writes requests, launch evidence, plans and continuation state;
workers write named outputs. Retain finished diagnoses; further work uses a new
numbered diagnosis. Verify the previous writer has stopped before transferring
an output. Current inputs are described by scope and paths, without content hashes.

## Execution environment

Keep environments, caches, disposable fixtures and temporary build workspaces
outside the consuming project and skill collections. Preserve inherited
`UV_CACHE_DIR` and `UV_TOOL_DIR`. If absent, resolve the OS temporary directory
through its API and set absolute `uv-runtime/cache` and `uv-runtime/tools` paths
for the process. Create them and check `uv cache dir` plus actual create/write/read/list
access. Reapply these variables and `PYTHONDONTWRITEBYTECODE=1` in new shells.

Find Python once: `uv python find --system --no-managed-python ">=3.11"`.
Use its absolute path in every run. Entry points have PEP 723 metadata and adjacent
lockfiles; the consuming project needs no Python environment or dependencies.

```text
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --repository "<project-root>" --get investigation.candidate_group_limit
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" configure --repository "<project-root>" --input "<external-temporary-dir>/collection-candidate.json" --output "<report-dir>/collection-input.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" collect --repository "<project-root>" --config "<report-dir>/collection-input.json" --output "<report-dir>"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --collection "<report-dir>/collection.json" --get recommendations.report_limit
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" rank --repository "<project-root>" --collection "<report-dir>/collection.json" --recommendations "<report-dir>/cards.json" --output "<report-dir>/ranked-1.json" --markdown "<report-dir>/ranked-1.md"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" status --repository "<project-root>" --collection "<report-dir>/collection.json"
```

`configure` reads candidate JSON from `--input` or stdin and validates before
writing the audit's `collection-input.json`. It rejects absolute paths on either
OS, drive-relative paths, parent traversal and host paths embedded in provenance.
It can update the input only before collection artifacts exist; started collections
retain their configuration. Use this helper for every configuration write.
`collect` revalidates input and checks resolved project paths, including symlinks.

`policy` is the read-only numerical-settings interface for agents. `collect` prepares the complete catalog, selections, preliminary groups and their
queue before substantive analysis. Its stdout gives the path to `collection.json`
and counts of outputs, candidate groups and gaps. Gap details are in the file. `rank` runs
after cards are authored; it checks their six-section Markdown structure and reads
only cited metric files and current source paths. Narrative stays in the Markdown
cards; JSON carries addresses, statuses and effects for ranking.
Generated Markdown is an input to the final report; the assigned architect authors
`report.md`. Existing ranked output files are rejected to preserve retained results.
`status` runs only after report and plan completion. For an explicitly focused route,
add `--focused` to `collect`; that collection cannot publish project status.

Register resolved commands, cwd, paths, expected outputs and limits in
`collection-plan.md` before assigning checks. Execute only the exact assigned set.
Python scripts use the standard library. Keep `--locked`; update Python lockfiles
only for an intentional dependency change. Find Java via runtime `--java`, PATH or
JAVA_HOME. Kotlin collection uses JDK 17+ and one of the existing detekt runtimes:

- By default, use the project's Gradle wrapper. The invocation-only
  `detekt-runtime.init.gradle` exports the selected project's existing `detekt`
  dependency configuration. `--detekt-project :server` selects a subproject;
  the default is `:`. No plugin, dependency or task is written to the project.
  Gradle may resolve missing dependencies using the project's configured repositories.
- `--detekt-jar <absolute-path>` selects an existing detekt CLI `all.jar` directly.
  It is an explicit runtime selection for projects without a usable wrapper or
  Gradle configuration. The collector never downloads a replacement detekt.

Probe the actual runtime with `--version`. Select the matching JAR from `bin/`
using [plugins.json](../bin/plugins.json): detekt 1.x needs at least 1.23.8;
detekt 2.x needs at least 2.0.0-alpha.6. Later releases of the same major are admitted
without an exact version pin. A lower version or an unknown major is an error.
The minimum versions are also the API baselines used to build the adapters;
admission of a later release is not evidence that its ABI was tested.

Run the resolved detekt CLI with the selected plugin and the exact Kotlin source
inventory. The plugin receives the host's parsed files through `FileProcessListener`
and emits `sdd-architect-measurements` through `OutputReport`. This separate measurement
invocation disables default rule sets and does not inherit warning thresholds,
baselines or suppressions that would remove functions from the population. The
project's ordinary detekt SARIF remains a separate input.

Record actual detekt, Kotlin parser and plugin versions plus the measurement profile
in the report. Runtime resolution, plugin loading, syntax errors or incomplete
file coverage block collection. Do not switch runtimes to bypass an error. JVM
argument files, the source manifest, exported runtime, Gradle project cache and
temporary report stay outside the project/package; retain the accepted report
once in the audit's `raw/`. The two bundled plugin JARs are deliberate package
artifacts; other build output and third-party JARs remain external.

On filesystem errors, report the first failing path. Probe with the same interpreter
and launch method, then use the host's normal permission mechanism if necessary.
Preserve sandbox and ACLs. Windows commands launched by the collector are hidden;
timeouts stop their process trees. Report command text is never executed implicitly.

## Continuation state commands

The orchestrator runs this helper directly; it does not dispatch state maintenance
to a worker. These commands are the exclusive agent interface to saved `state.json`:
read through `read`, prepare the changed document, and persist through `write`.
Use `check` for material consistency. Use the same system Python and uv environment
as the metric commands:

```text
uv run --python "<python>" --locked --script "<skill>/scripts/audit_state.py" read --report-dir "<report-dir>"
uv run --python "<python>" --locked --script "<skill>/scripts/audit_state.py" check --report-dir "<report-dir>"
uv run --python "<python>" --locked --script "<skill>/scripts/audit_state.py" write --report-dir "<report-dir>" --input "<external-temporary-dir>/state-input.json"
```

`write` also accepts the whole JSON document on stdin when `--input` is omitted.
Prepare candidates outside the project/package, preserve exact user constraints,
and use `write` for each update. It validates the schema and internal relationships,
flushes a temporary sibling in the audit directory and atomically replaces
`state.json`; it cleans up the sibling when the operation returns. A failure before
replacement preserves the old file. The orchestrator is the only writer.

`read` validates and returns the saved JSON. `check` additionally verifies linked
material through the [continuation contract](continuation.md#save-continuation-state)
and returns `valid` and `issues`, with a nonzero exit code for issues. `write` applies
these material checks before saving `phase: complete`. Saving unfinished state is
possible while linked evidence is unavailable, so recovery work can be retained.
Run `check` before dependent work and obtain fresh host observations on resumption.

## Developer validation

Run `scripts/test.py` with the same uv invocation. Set absolute external paths:
`ARCHITECT_TEST_JAVA` to JDK 17+, `ARCHITECT_TEST_DETEKT1_JAR` and
`ARCHITECT_TEST_DETEKT2_JAR` to the two baseline CLI `all.jar` distributions,
and `ARCHITECT_TEST_GRADLE_WRAPPER` to an existing wrapper JAR with adjacent
wrapper properties. The mandatory JVM scenarios verify both SPI/PSI APIs and
new context parameters; one Gradle subproject verifies runtime discovery.
Version boundaries and formula/rule combinations run without subprocesses.
Plugin sources and the reproducible build command live in the repository's
`tools/detekt-measurements/`; rebuild both bundled JARs after changing those sources.
The publication scenario
checks real status files in an external temporary directory. The full
sequential deterministic suite has a 120-second wall-clock budget including setup
and launch. Stop its process tree and work if the limit is exceeded. Keep test logs
and fixtures outside the project and package. Behavior scenarios require separate
explicit consent under project instructions.
