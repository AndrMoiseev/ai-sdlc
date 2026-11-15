# Collect or import measurements

## Collection in the default full cycle

Use this reference during configuration and collection in the [workflow](workflow.md).
Explorer researches the current checkout; the orchestrator saves this audit's configuration
and registers exact build/report commands. A fresh explorer executes the assigned
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
   into this audit's `raw/` before referring to them. Pass the project root and
   external Java/detekt locations only as runtime arguments, never as configuration.
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
| `artifacts` | Required `dependencies`, `history`, `sizes`, `kotlin`, `complexity`, `coverage` inputs |

All configuration paths are relative to the runtime `--repository`, independently
of cwd or the configuration's directory. The configuration has no `repository` field.
`artifacts.*.source_root` is project-relative (`.` by default); report source paths
must already be project-relative or refer to that root in the current checkout.
Qualify exports from another machine before import; do not save their old absolute
root in configuration. Source paths in JSONL use repository-relative `/` paths.
Module prefixes match package segments; the longest prefix wins. Equal longest
prefixes assigned to different modules block a full audit.

## Obtain missing reports

Resolve [analysis policy](analysis-policy.md) through the script before choosing
collection conditions. Read numerical policy from its separate project file; preserve
detector settings that collect a sufficiently complete population. `collect` applies
analyzer thresholds after import, including the parameter-list threshold.

Register exact commands, outputs and limits in the collection plan before assigning
checks. Existing build/report tasks run before their dependent `collect` command.
The collector supports its fixed jdeps, Git, scc and Kotlin measurement commands; a report's stored
command is descriptive provenance, never an executable command string.

1. Discover existing Gradle compilation, detekt and JaCoCo tasks. Read their actual
   configuration. An absent required task is a blocker; configuring it is separate work.
   Use external caches and temporary build output where the project supports them.
2. Compile the selected production code and consumers. `dependencies: {"collect": true}`
   invokes `jdeps -verbose:class -filter:none --ignore-missing-deps` on configured
   directories. DI, reflection and missing dependencies limit graph completeness.
   `collect` does not compile the project.
3. `history: {"collect": true}` exports the policy window through the current UTC
   date, first-parent only, excluding merges and tracking Git-detected renames.
   Shallow history blocks collection. Retain complete changesets and their production
   file counts before filtering. Historical commit IDs address events only.
   Focused collection can use `since`/`until` and the simpler `git-log` import.
4. `sizes: {"collect": true}` invokes scc JSON with per-file rows across the repository.
   Aggregate files, lines, code, comments and blanks by language, production/test/other
   category and module. Exclude configured generated/build paths and `memory/tech-debt/**`.
   scc Complexity is not cognitive complexity and is not an input to L.
5. Obtain detekt SARIF for the five supported rules. The adapter understands the
   recorded detekt 1.23.8 message forms; another form leaves a value unknown.
   Retain locations, declarations and suppressions. Set `complete_mcc: true` only
   with evidence that the selected function population was fully measured.
6. Run selected tests and obtain one merged JaCoCo XML. Merge execution data with
   the coverage tool; do not add duplicate source rows from separate reports.
   Set `complete: true` and `test_result: "passed"` only after checking complete
   production class coverage and successful execution of the configured test tasks.
   Missing reports, classes or required counters block a full audit.
7. `kotlin: {"collect": true}` runs the bundled token/function collector with detekt's
   Kotlin parser and cognitive-complexity implementation. This supplies all named
   functions, including zero values and suppressed findings, plus token positions
   and size containers. Optional runtime `--java` and `--detekt-jar` select the JDK
   launcher and the required detekt 1.23.8 distribution. See [runtime](runtime.md).
   No project Kotlin version is prescribed; unsupported syntax blocks collection.

Record `format`, `tool`, `version`, `command`, `source_root`, and relevant limitations
for imports. Save original reports once in `raw/`; tools may write directly there.
The collector reuses a raw input already in the destination instead of copying it.
It saves a separate normalized representation in `metrics/`, never a second raw copy.

## Import existing reports

For reused reports or an explicitly [focused route](continuation.md#explicit-focused-routes),
qualify populations, tool definitions, exclusions, source paths and mapping. Assign
`collect --focused` for an explicitly focused route; use plain `collect` for a
full audit with every required source. Never choose focused mode to bypass a blocker.

| Input | Accepted format |
| --- | --- |
| Dependencies | `class-csv` with `from,to`, or `jdeps` text |
| History | Full audit: `git-history` JSON produced by the collector, covering the policy window; focused work also accepts `git-log` |
| Size | `scc` per-file JSON |
| Complexity | `detekt-sarif` |
| Kotlin | Complete `kotlin-measurements` JSON produced by the bundled collector |
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
