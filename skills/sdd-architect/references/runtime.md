# Runtime and storage

Use `uv` and a system Python 3.11+. Git is required only for requested history
collection; jdeps and scc only for their respective branches. detekt and JaCoCo
tasks belong to the consuming project. Missing tools limit their own chains.

## Report storage

Before producing materials, establish `<project-root>/docs/reports/{report-name}/`
and use its absolute path as `<report-dir>`. Use the requested name or a descriptive
kebab-case name. Choose an unused numeric suffix for an unrelated report with the
same name. Continue an existing audit through its saved state and current inputs.

| Material | Location relative to `<report-dir>` |
| --- | --- |
| Final report and continuation state | `report.md`, `state.md` |
| Collection plan | `collection-plan.md` |
| One retained copy of each raw input and tool logs | `raw/`, `logs/` |
| Collection parameters, output links and outcomes; no value tables | `collection.json` |
| One metric at one granularity | `metrics/<metric>/<granularity>.jsonl` |
| Keyed sorting and threshold selections | `selections/rankings.jsonl`, `selections/signals.jsonl` |
| Candidate shortlist and diagnosis index | `diagnosis.md` |
| Separate bounded diagnoses | `diagnoses/<group-id>/diagnosis-<n>.md` |
| Saved assignment, launch and worker result | `assignments/<assignment-id>/request.json`, `launch.json`, `result.json` |
| Authored cards, validated ordering and optional rendered table | `cards.json`, `ranked-<n>.json`, `ranked-<n>.md` |

Source paths are relative to the project with `/`; links between retained materials
are relative to their report directory. Resolve writes inside the intended report,
including symlinks. `collect --output` accepts the report directory itself, including
pre-existing `raw/` and plans, but rejects an existing `collection.json`, `metrics/`
or `selections/`. Further collection uses a new named report directory, linked from
the audit being continued. Do so only for a measurement need, never a version check.

There are no monolithic measurement exports or copied source trees. Keep the current
configuration at `.sdd/architect/collection.json`; `collection.json` in the report
records the used measurement parameters. Source-free input settings instead use
`collection-input.json` beside the output. Existing external reports are copied
once into `raw/`; inputs already there are reused directly.

Retain partial outputs and concrete gaps. The collection description starts with
`status: incomplete` and every planned output marked incomplete. Normal completion
accounts for each output as `complete`, `unavailable` or `error`; an interrupted
calculation remains distinguishable from a successful empty JSONL file. Outcome
metadata, parameters and gaps stay outside metric rows.

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
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" collect --config "<project-root>/.sdd/architect/collection.json" --output "<report-dir>"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" rank --collection "<report-dir>/collection.json" --recommendations "<report-dir>/cards.json" --output "<report-dir>/ranked-1.json" --markdown "<report-dir>/ranked-1.md"
```

`collect` prepares the complete catalog and selections before substantive analysis.
Its stdout reports counts, the collection-description path and gaps. `rank` runs
after cards are authored; it reads only cited metric files and current source paths.
Generated Markdown is an input to the final report; the assigned architect authors
`report.md`. Existing ranked output files are rejected to preserve retained results.

Register resolved commands, cwd, paths, expected outputs and limits in
`collection-plan.md` before assigning checks. Execute only the exact assigned set.
The scripts use the standard library; no package download is required, including
empty-cache or deliberately offline execution. Keep `--locked`; update lockfiles
only for an intentional dependency change.

On filesystem errors, report the first failing path. Probe with the same interpreter
and launch method, then use the host's normal permission mechanism if necessary.
Preserve sandbox and ACLs. Windows commands launched by the collector are hidden;
timeouts stop their process trees. Report command text is never executed implicitly.

Developer validation runs `scripts/test.py` with the same uv invocation. The full
sequential deterministic suite has a 120-second wall-clock budget including setup
and launch. Stop its process tree and work if the limit is exceeded. Keep test logs
and fixtures outside the project and package. Behavior scenarios require separate
explicit consent under project instructions.
