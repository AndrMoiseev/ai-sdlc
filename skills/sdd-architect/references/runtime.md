# Runtime and storage

Use `uv` and a system Python 3.11+. Full audits require Git, jdeps, scc, a JDK source
launcher, the bundled Kotlin measurement helper and complete detekt/JaCoCo reports.
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
`memory/tech-debt/status.json` and `status.md` under the
[publication contract](quality-indicators.md#publication).

| Material | Location relative to `<report-dir>` |
| --- | --- |
| Final report and continuation state | `report.md`, `state.md` |
| Collection plan | `collection-plan.md` |
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

The aggregate document is separate from keyed JSONL diagnostics. Do not copy source trees. Keep the current
configuration at `.sdd/architect/collection.json`; `collection.json` in the report
records the used measurement parameters and resolved [analysis policy](analysis-policy.md).
Project numerical overrides live in `.sdd/architect/analysis-policy.json`. Source-free input settings instead use
`collection-input.json` beside the output. Existing external reports are copied
once into `raw/`; inputs already there are reused directly.

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
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --repository "<project-root>"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" collect --config "<project-root>/.sdd/architect/collection.json" --output "<report-dir>"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --collection "<report-dir>/collection.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" rank --collection "<report-dir>/collection.json" --recommendations "<report-dir>/cards.json" --output "<report-dir>/ranked-1.json" --markdown "<report-dir>/ranked-1.md"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" status --collection "<report-dir>/collection.json"
```

`policy` is the sole numerical-settings interface for agents. `collect` prepares the complete catalog, selections, preliminary groups and their
queue before substantive analysis. Its stdout reports counts, including candidate
groups, the collection-description path and gaps. `rank` runs
after cards are authored; it checks their six-section Markdown structure and reads
only cited metric files and current source paths. Narrative stays in the Markdown
cards; JSON carries addresses, statuses and effects for ranking.
Generated Markdown is an input to the final report; the assigned architect authors
`report.md`. Existing ranked output files are rejected to preserve retained results.
`status` runs only after report and plan completion. For an explicitly focused route,
add `--focused` to `collect`; that collection cannot publish project status.

Register resolved commands, cwd, paths, expected outputs and limits in
`collection-plan.md` before assigning checks. Execute only the exact assigned set.
Python scripts use the standard library. The Kotlin helper executes Java source
against detekt CLI 1.23.8 `all.jar`; it does not modify project build dependencies.
Find Java via `artifacts.kotlin.java`, PATH or JAVA_HOME. The helper needs JDK 11+
source-launcher support. It downloads the fixed Maven distribution into
`UV_TOOL_DIR/sdd-architect/` if absent. For offline use provide the existing jar's
absolute path as `artifacts.kotlin.detekt_jar`. Keep the jar, temporary source
manifest and JVM caches outside the project and skill package. Record detekt's
measurement version independently of the project's Kotlin version. A download,
launch or syntax failure blocks collection. Keep `--locked`; update Python
lockfiles only for an intentional dependency change.

On filesystem errors, report the first failing path. Probe with the same interpreter
and launch method, then use the host's normal permission mechanism if necessary.
Preserve sandbox and ACLs. Windows commands launched by the collector are hidden;
timeouts stop their process trees. Report command text is never executed implicitly.

Developer validation runs `scripts/test.py` with the same uv invocation. Set
`ARCHITECT_TEST_JAVA` to the JDK launcher and `ARCHITECT_TEST_DETEKT_JAR` to the
detekt 1.23.8 `all.jar`, both absolute paths outside the package. The mandatory
single JVM scenario verifies actual parser/metric integration; the remaining
formula/rule combinations run without subprocesses. The publication scenario
checks real status files in an external temporary directory. The full
sequential deterministic suite has a 120-second wall-clock budget including setup
and launch. Stop its process tree and work if the limit is exceeded. Keep test logs
and fixtures outside the project and package. Behavior scenarios require separate
explicit consent under project instructions.
