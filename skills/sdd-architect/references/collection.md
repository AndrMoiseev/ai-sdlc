# Collect or import measurements

## Collection in the default full cycle

Use this reference during configuration and collection in the [workflow](workflow.md).
Explorer researches the current checkout; the orchestrator saves the configuration
and registers exact build/report commands. A fresh explorer executes the assigned
checks. `collect` then retains raw reports, normalizes each source once, computes
all derived measurements and prepares keyed selections before architects begin
substantive analysis. Read individual JSONL files through `collection.json`.

Inventory dependencies, history, size, complexity and coverage. Each catalog output
ends with a result or a concrete reason for unavailability. A failing source limits
its dependent calculations; independent chains continue. Successful execution does
not imply that all observations were available or complete.

## Establish the scope

Read the project's build scripts, architecture decisions, package conventions,
ArchUnit checks and vocabulary. Choose production Kotlin/Java source roots,
compiled directories, variants, test tasks and exclusions from that evidence.
Android and Multiplatform require an explicit JVM variant/source-set choice.
Keep test/generated code separate from the measured graph; inspect generated
wiring when it explains behavior. Undeclared packages remain unassigned.
Gradle layout establishes build scope, not architectural responsibility.

## Maintain project configuration

The orchestrator maintains `<project-root>/.sdd/architect/collection.json` on every
run with sources, including imports. Explorer proposes changes without editing
project configuration or `.sdd/settings.json`.

1. Read the configuration or initialize it from
   [collection.example.json](../assets/collection.example.json).
2. Check source roots, compiled directories, package prefixes, module ownership,
   exclusions, build scope and test tasks against current project evidence.
   Preserve deliberate boundaries and the history window unless the task calls
   for a different measurement population. Unknown ownership remains unassigned.
3. Resolve current source and report paths. Record tool versions, actual commands,
   populations, exclusions and extraction limitations; these describe the measurement.
4. Save the configuration and `collection-plan.md` before the assigned collection.
   Refresh paths or settings when the task requires them; an unchanged configuration
   needs no rewrite. Explain scope changes in the final report.

The audit does not capture or verify a source version. It uses current sources and
supplied reports directly, without revision, cleanliness, fingerprint or checksum
requirements. Missing or different identifiers never reduce suitability, require
recollection, or prevent readiness. The future commit containing audit materials
is their ordinary repository history, not an input to this process.

| Configuration field | Meaning |
| --- | --- |
| `repository`, `source_roots`, `exclude_paths` | Checkout and production population; exclusions are case-sensitive glob patterns |
| `package_prefixes`, `exclude_classes` | Internal graph namespace and class exclusions; nested JVM names stay distinct |
| `modules` | Declared module names mapped to package prefixes; `{}` means ownership is unknown |
| `scope` | Gradle projects, source sets, variant and test tasks |
| `class_directories` | Compiled directories for jdeps and JVM SourceFile mapping |
| `class_files` | Optional explicit JVM-class to repository-relative source mapping |
| `artifacts` | Available dependencies, history, sizes, complexity and coverage inputs |

Artifact import paths are absolute. Source roots and compiled directories are
relative to `repository`. Source paths in JSONL use repository-relative `/` paths.
Module prefixes match package segments; the longest prefix wins. Equal longest
prefixes assigned to different modules make module-dependent calculations unavailable.

## Obtain missing reports

Register exact commands, outputs and limits in the collection plan before assigning
checks. Existing build/report tasks run before their dependent `collect` command.
The collector supports its fixed jdeps, Git and scc commands; a report's stored
command is descriptive provenance, never an executable command string.

1. Discover existing Gradle compilation, detekt and JaCoCo tasks. Read their actual
   configuration. Record an absent task as a gap; configuring it is separate work.
   Use external caches and temporary build output where the project supports them.
2. Compile the selected production code and consumers. `dependencies: {"collect": true}`
   invokes `jdeps -verbose:class -filter:none --ignore-missing-deps` on configured
   directories. DI, reflection and missing dependencies limit graph completeness.
   `collect` does not compile the project.
3. `history: {"collect": true, "since": "YYYY-MM-DD"}` exports available Git history
   with `--no-merges --no-renames --numstat`; `until` is optional. Preserve full
   changeset sizes before filtering co-change support. A historical commit ID
   addresses a change event only. Git is needed solely for this collection branch.
4. `sizes: {"collect": true}` invokes scc JSON with per-file rows. Normalize `Code`
   and `Lines`; comments, blanks and scc Complexity remain outside the core catalog.
5. Obtain detekt SARIF for the five supported rules. The adapter understands the
   recorded detekt 1.23.8 message forms; another form leaves a value unknown.
   Retain locations, declarations and suppressions. Set `complete_mcc: true` only
   with evidence that the selected function population was fully measured.
6. Run selected tests and obtain one merged JaCoCo XML. Merge execution data with
   the coverage tool; do not add duplicate source rows from separate reports.

Record `format`, `tool`, `version`, `command`, `source_root`, and relevant limitations
for imports. Save original reports once in `raw/`; tools may write directly there.
The collector reuses a raw input already in the destination instead of copying it.
It saves a separate normalized representation in `metrics/`, never a second raw copy.

## Import existing reports

For reused reports or an explicitly [focused route](continuation.md#explicit-focused-routes),
qualify populations, tool definitions, exclusions, source paths and mapping. Assign
`collect` to complete normalization and calculation before source interpretation.

| Input | Accepted format |
| --- | --- |
| Dependencies | `class-csv` with `from,to`, or `jdeps` text |
| History | `git-log` with complete changesets and numstat |
| Size | `scc` per-file JSON |
| Complexity | `detekt-sarif` |
| Coverage | `jacoco` XML or `coverage-csv` with covered/total counters |

Set `source_root` to the checkout root encoded in imported paths. Unresolved paths
are an adapter gap; joining by basename would invent a correspondence. A coupling
export alone cannot recover exact support; request its log only if that could
change the decision. Missing tool or command provenance limits interpretation,
without any comparison to a source version.

With no sources, use the destination project directory as `repository` and empty
source/class directories. Keep input settings in `<report-dir>/collection-input.json`;
`collection.json` is reserved for the output description. Calculations remain useful,
but implementation readiness requires inspected current declarations and consumers.
End source-free work with hypotheses, decision-relevant questions and `report.md`.

## Mapping and suitability

JVM SourceFile plus package identifies source candidates, including top-level
functions, custom facades, nested classes, objects and companions. Duplicate source
filenames within a package remain ambiguous across source sets. Explicit overrides
require a real class/file correspondence, without a version marker.

Inspect mapping gaps before file hotspots or claims about absent direct static edges.
A partial mapping limits those claims while leaving independent graph/history results
available. SARIF locations are observations: inspect current declarations and overload
signatures before recommending a transformation. Use substantive evidence and the
[measurement catalog](measurements.md) to establish applicability.
