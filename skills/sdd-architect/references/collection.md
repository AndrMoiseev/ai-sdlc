# Collect or import measurements

## Collection in the default full cycle

Use this reference during configuration and collection in the [workflow](workflow.md).
Explorer researches the current checkout; the orchestrator saves this audit's configuration
and registers the collection check. A fresh explorer executes the assigned
checks. `collect` then retains raw reports, normalizes each source once, computes
all derived measurements and prepares keyed selections, preliminary candidate groups
and their investigation queue before architects begin
substantive analysis. Read individual JSONL files through `collection.json`.

Inventory dependencies, history, scc statistics, Kotlin tokens/functions, detekt
diagnostics and JaCoCo coverage. All six sources are mandatory for a full audit.
Missing, failed or incomplete input blocks it. Explain the prerequisite and propose
resolving it first; preserve the previous status. Only explicitly focused work may
retain partial inputs under its narrower contract.

## Establish the scope

Read the project's build scripts, architecture decisions, package conventions,
ArchUnit checks and vocabulary. Choose production Kotlin/Java source roots,
compiled directories, variants, test tasks and exclusions from that evidence.
Android and Multiplatform require an explicit JVM variant/source-set choice.
Keep test/generated code separate from the measured graph; inspect generated
wiring when it explains behavior. Assign every measured Kotlin package to a declared
architectural module before a full audit; ambiguous or missing ownership blocks it.
Gradle layout establishes build scope, not architectural responsibility.

## Prepare audit configuration

The orchestrator owns `<report-dir>/collection-input.json` for every route.
Explorer proposes its contents. Project settings, including `.sdd/` and build
configuration, remain read-only for both roles. Their modification belongs to
user-initiated `sdd-setup`, even when the user would approve an audit-time edit.
If setup lacks an option, report that limitation without adding an audit workaround.

1. Establish the audit directory and start from
   [collection.example.json](../assets/collection.example.json).
   In a new audit, treat prior configurations as research leads and check every
   reused choice against current project evidence and the current request.
   Distinguish user constraints from an earlier researcher's choices.
2. Establish source roots, compiled directories, package prefixes, module ownership,
   exclusions, build scope and test tasks. The full-audit history window comes
   from the resolved quality-indicator policy. Focused analysis may retain its own window.
3. Express every configuration path relative to the project root using `/`;
   `.` denotes the root. This includes imported reports, source roots, class mappings,
   exclusions and paths inside command arguments. Absolute paths, drive-relative
   paths, file URIs and parent traversal are rejected. Stage external reports once
   into this audit's `raw/` before referring to them. Always
   pass the project root as a runtime argument.
4. Prepare candidate JSON on stdin or in external temporary storage. Save it only
   through `metrics.py configure` under the [runtime contract](runtime.md).
   The helper validates before writing `collection-input.json`; `collect` checks
   it again before measurements. Save `collection-plan.md` beside it.
   The helper allows updates before collection and preserves configuration once
   collection has started. Recollection uses a new audit directory.

Continue an interrupted audit with its own configuration after checking current
conditions. A new audit always gets its own configuration, even when values match.
Explain changed scope in the report; do not promote research results to project settings.

The audit does not capture or verify a source version. It uses current sources and
supplied reports directly, without revision, cleanliness, fingerprint or checksum
requirements. Missing or different identifiers never reduce suitability, require
recollection, or prevent readiness. The future commit containing audit materials
is their ordinary repository history, not an input to this process.

| Configuration field | Meaning |
| --- | --- |
| `source_roots`, `exclude_paths` | Project-relative production population; exclusions are case-sensitive glob patterns |
| `test_roots`, `statistics_exclude_paths` | Test classification and additional exclusions for repository-wide scc statistics |
| `package_prefixes`, `exclude_classes` | Internal graph namespace and class exclusions; nested JVM names stay distinct |
| `modules` | Architectural module names mapped to package prefixes; complete ownership is mandatory in full audits |
| `scope` | Gradle projects, source sets, variant and test tasks |
| `class_directories` | Compiled directories for jdeps and JVM SourceFile mapping |
| `class_files` | Optional explicit JVM-class to repository-relative source mapping |
| `artifacts` | Supplied report descriptors for focused import only. Omit for fresh collection. |

All configuration paths are relative to the runtime `--repository`, independently
of cwd or the configuration's directory. The configuration has no `repository` field.
`artifacts.*.source_root` is project-relative (`.` by default); report source paths
must already be project-relative or refer to that root in the current checkout.
Qualify exports from another machine before import; do not save their old absolute
root in configuration. Source paths in JSONL use repository-relative `/` paths.
Module prefixes match package segments; the longest prefix wins. Equal longest
prefixes assigned to different modules block a full audit.

## Project collection command

Full audits and focused work that needs fresh measurements read
`architect.collection` from `.sdd/settings.json` (schema version 1). It contains
`command`, an executable and its arguments as a JSON array, and `artifacts`,
a map of the six named reports to project-relative paths, formats and qualifications.
Read it with `metrics.py collection-settings --repository <project-root>` before starting
fresh collection. Only `sdd-setup` writes this setting. Missing or invalid settings stop fresh collection
before the command starts. Direct the user to run `sdd-setup` to configure audit collection.

Save only the researched scope in the audit configuration for fresh collection.
Register `metrics.py collect` as one check. It invokes the saved argument array
once from the project root, then imports the six reports. Do not separately invoke
the command, a build task, a report producer or a per-source fallback. Record the
actual failure if the command exits unsuccessfully. A missing output identifies
the report name and path to fix. Preserve the previous published status.

Use `collect --focused --fresh` when focused work actually needs new measurements.
Use `collect --focused` with audit-local `artifacts` for supplied reports. Reading
retained evidence and resuming later phases do not rerun the command.

## Import existing reports

For reused reports or an explicitly [focused route](continuation.md#explicit-focused-routes),
qualify populations, tool definitions, exclusions, source paths and mapping. Assign
`collect --focused` for an explicitly focused route; use plain `collect` for a
full audit with every required source. Never choose focused mode to bypass a blocker.

| Input | Accepted format |
| --- | --- |
| Dependencies | `class-csv` with `from,to`, or `jdeps` text |
| History | Full audit: `git-history` JSON produced by the project command, covering the policy window; focused work also accepts `git-log` |
| Size | `scc` per-file JSON |
| Complexity | `detekt-sarif` |
| Kotlin | Complete `kotlin-measurements` JSON, schema 2 and the declared measurement profile, from the project detekt measurement report |
| Coverage | Full audit: complete `jacoco` XML; focused work also accepts `coverage-csv` |

Set `source_root` to the checkout root encoded in imported paths. Unresolved paths
are an adapter gap; joining by basename would invent a correspondence. A coupling
export alone cannot recover exact support; request its log only if that could
change the decision. Missing tool or command provenance limits interpretation,
without any comparison to a source version.

With no sources, pass the destination project directory as runtime `--repository`
and use empty source/class directories. Keep configuration in `<report-dir>/collection-input.json`;
`collection.json` is reserved for the output description. Calculations remain useful,
but implementation readiness requires inspected current declarations and consumers.
End source-free work with hypotheses, decision-relevant questions and `report.md`.

## Mapping and suitability

JVM SourceFile plus package identifies source candidates, including top-level
functions, custom facades, nested classes, objects and companions. Duplicate source
filenames within a package remain ambiguous across source sets. Explicit overrides
require a real class/file correspondence, without a version marker.

Inspect mapping gaps before file hotspots or claims about absent direct static edges.
A partial mapping blocks a full audit. In focused work it limits the affected claims.
SARIF locations are observations: inspect current declarations and overload
signatures before recommending a transformation. Use substantive evidence and the
[measurement catalog](measurements.md) to establish applicability.
