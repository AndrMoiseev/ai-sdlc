# Collect or import measurements

## Collection in the default full cycle

Use this reference in the configuration and evidence phases of the
[four-phase workflow](workflow.md). Explorer researches the current checkout and
proposes inputs from its build and source tree; the orchestrator saves the
configuration and plan. Fresh explorer executes the assigned measurement commands
through the checks contract in the evidence phase.

Inventory all five measurement families: dependencies, Git history,
source size, complexity and coverage. Obtain each applicable family with the
available tools and existing project tasks, recording a concrete gap for any
unavailable family. Reuse a report only after checking its scope and source identity.
Create the current snapshot with `collect`, then continue with `analyze`, source
diagnosis and recommendation delivery. The collection plan and raw reports are
intermediate results of this route.

## Establish the scope

Read the project's build scripts, architecture decisions, package conventions,
ArchUnit checks and domain vocabulary. Propose production Kotlin/Java source roots,
compiled class directories, variants, test tasks and exclusions from that evidence.
Android and Multiplatform require an explicit JVM variant/source-set decision;
do not silently treat native or common sources as a JVM bytecode graph.

Keep test/generated code separate. Include generated wiring in code investigation
when it explains runtime behavior, even if it is excluded from the measured graph.
An undeclared package stays unassigned; it is not a shared `legacy` module.
Infer neither package responsibilities nor architectural modules from Gradle layout.

## Maintain project configuration

Use `<project-root>/.sdd/architect/collection.json` as the project's collection
configuration. The orchestrator applies this maintenance from explorer's sourced
proposal on every run with a project checkout, including runs that reuse existing
reports. Explorer returns proposed changes without editing configuration or settings:

1. Read the existing file. If absent, create its parent directory and initialize
   it from [collection.example.json](../assets/collection.example.json), replacing
   the example values with evidence from the current project.
2. Recheck source roots, compiled directories, measurement inputs, package
   prefixes, module ownership, exclusions, Gradle scope and test tasks against
   the current source tree, build and architecture decisions. Reconcile additions,
   moves and removals. Preserve deliberate boundaries, exclusions and the history
   window unless project evidence or the requested analysis justifies changing them.
   Leave packages with unknown ownership unassigned.
3. Refresh checkout and artifact paths for this run. Verify reused bytecode,
   class mappings and reports against their actual source identities; retain
   their original provenance and leave unknown values null. Saving the
   configuration does not make an older report current.
4. Save the reconciled configuration and `collection-plan.md` before capturing
   source identity. As new
   compilation or reports establish provenance, save those verified values before
   `collect`. Keep the configuration stable during each `identity` or `collect`
   command. Replace only changed values; an already current file needs no rewrite.
5. In the final report, state whether the configuration was created, updated or
   already current, and summarize changes to the analysis scope or definitions.

This file is maintained project configuration, separate from `.sdd/settings.json`,
which configures SDD subagents. Save the collection plan, captured identity,
snapshots, raw reports and logs in the current report directory following
[report storage](runtime.md#report-storage).
Keep the collection configuration itself out of `measurement_inputs`: it contains
the resulting source-state identifiers, and `collect` already records its contents
in the snapshot.

All artifact paths are absolute; source roots, compiled directories and measurement
inputs are relative to `repository`. Module prefixes match package segments; the
longest matching prefix wins. Equal prefixes assigned to different modules are errors.

| Configuration field | Meaning |
| --- | --- |
| `repository`, `source_roots`, `exclude_paths` | Exact checkout and production source population; exclusions are case-sensitive glob patterns |
| `measurement_inputs` | Build scripts, analyzer configurations, version catalog and other files that define the measurement; included in the source fingerprint |
| `package_prefixes`, `exclude_classes` | Internal graph namespace and explicit class exclusions; JVM nested names are preserved |
| `modules` | Declared module names mapped to package prefixes; use `{}` when ownership is unknown |
| `scope` | Gradle projects, source sets, variant and test tasks as collection provenance |
| `class_directories` | Compiled directories from the selected build; needed for jdeps and SourceFile mapping |
| `class_files`, `class_files_source_state` | Optional verified JVM-class → repository-relative source overrides and the source identity actually checked |
| `artifacts` | Any available subset of dependencies, history, sizes, complexity and coverage |

Use `identity` before a measurement run to obtain `revision`, `dirty` and
`source_state`. The fingerprint covers selected source contents and measurement
inputs, including uncommitted source changes. Record the complete actual scope;
the fingerprint cannot detect an omitted input. Keep sources and measurement
inputs stable through compilation, tests, collection and source review. Report
writes can change Git's dirty flag without changing the measured source identity.
Keep `docs/reports/` out of source roots and measurement inputs.

## Obtain missing reports

The orchestrator registers the exact commands, outputs and limits in the collection
plan and assigns them to explorer as checks. Return verified provenance to the
orchestrator for configuration updates before dependent `collect` execution.
If one measurement chain fails, preserve its gap and collect independent families
whose prerequisites remain valid. Use a new current checks assignment for unfinished
independent work when the original batch stops; reuse verified successful results.

1. Find the existing Gradle tasks for compilation, detekt and JaCoCo. Read their
   configuration before running them. Do not invent task names or change the
   consumer's dependencies merely to make the audit run. If a task is absent,
   record the gap and propose its exact configuration as a separate follow-up.
   Put caches and temporary build output outside
   the source checkout when the project's supported configuration permits it.
2. Compile the selected production code and consumers. Set `bytecode_source_state`
   to the identity actually compiled. For `dependencies: {"collect": true}`,
   the collector runs `jdeps -verbose:class -filter:none --ignore-missing-deps`
   over the configured class directories. `-filter:none` is necessary to retain
   dependencies inside an archive. Missing dependencies, DI and reflection still
   limit graph completeness. No compilation is performed by `collect`.
3. Set `history: {"collect": true, "since": "YYYY-MM-DD"}` for a bounded Git
   export ending at captured HEAD; `until` is optional. The collector uses
   `--no-merges --no-renames --numstat`. It records all changed paths before
   filtering large commits for coupling. Rename/delete histories require manual
   identity reconciliation; a disappeared path is not an improvement.
4. Set `sizes: {"collect": true}` to run scc JSON with per-file rows. The
   analysis selects `Lines`, `Code`, `Comment`, `Blank`; scc Complexity is unused.
5. Obtain detekt SARIF for the five selected rules. The reference adapter parses
   the recorded message forms of detekt 1.23.8. Record the actual tool version;
   another message form leaves a value unknown instead of guessing. Collection
   thresholds of 1 expose more of the row population, but suppressions, baselines
   and zero-valued cognitive complexity still prevent assuming a complete series.
   Set `complete_mcc: true` only after verifying full MCC coverage of the chosen
   population. Record the exact configurations and exclusions.
6. Run the selected tests and obtain one merged JaCoCo XML for the chosen scope.
   Duplicate source rows from separate reports must be merged by the coverage
   tool, not added by this script. Keep the tested source identity with the report.

Import the detekt and coverage paths with `format: "detekt-sarif"` and
`format: "jacoco"`. Set `revision`, `source_state`, `tool`, `version`, `command`
and report generation time from the actual run. A later import time never proves
that bytecode or coverage is current. Save logs/configuration paths in provenance.

## Import existing reports

Use this branch for inputs reused by the full cycle or an explicit
[focused route](continuation.md#explicit-focused-routes). A report's existence
does not select a focused route. With a checkout, maintain the project
configuration before identity capture; with no sources, use the import
configuration described below. In both cases the orchestrator records import
scope, artifact suitability and exact `collect`/`analyze` checks in the collection
plan and assigns them to explorer.

For each artifact, supply `path`, `format`, and `source_root` (the original checkout
root encoded in file URIs). Accepted dependency input is `class-csv` (`from,to`)
or `jdeps` text; history is `git-log`; sizes are per-file `scc` JSON; complexity
is `detekt-sarif`; coverage is `jacoco` or `coverage-csv` with covered/total counters.
An exported coupling table alone cannot recover exact support and is not used to
reconstruct history. Request its original log only if the pair can change a decision.

Leave unknown provenance fields null. `collect` copies raw inputs, records their
hashes and captures the current source inventory. `analyze` detects altered raw
files, mixed source identities and mixed revisions. Unknown identity limits the
related signal; known mismatches exclude it. Tool errors are recorded per artifact.
Read the gap list and verify that required reports actually arrived.
Unknown coverage remains unknown, not zero coverage. Qualify tool/configuration,
source population, mapping and generation provenance for each intended claim;
a current checkout does not make an older report suitable. Resolve only gaps that
can change the focused decision through [bounded evidence](continuation.md#request-bounded-evidence).

For source-free work, use the destination project directory as `repository`, with
`source_roots: []` and `class_directories: []`. Import supplied material by absolute
path and preserve its reported revision as provenance when known; do not invent
a checkout revision or substitute the destination's revision for an input's identity.
Keep the import configuration and results in the named report directory according
to [report storage](runtime.md#report-storage).
Graph calculations remain useful. Concrete implementation readiness is unavailable.
Continue with bounded hypotheses and the final report; preserve input provenance
and gaps even when every imported command succeeds.

## Mapping and suitability

JVM `SourceFile` attributes plus the exact package identify source candidates.
This handles top-level functions, custom file facades, multiple classes per file,
nested classes, objects and companions without equating class and file names.
Duplicate source filenames within a package remain ambiguous across source sets.
Inspect `mapping` before using a file hotspot or absence of a direct static edge.
An explicit mapping override needs source/build evidence and its checked
`class_files_source_state`. Automatically read mappings carry
`bytecode_source_state`. Unknown mapping identity limits file joins; a known
mismatch excludes mappings, preserving the independently usable graph/history.

Imported reports with unresolved absolute paths fail their adapter with an explicit
gap. Never join by basename. SARIF locations are observations at a revision, not
stable function identities: inspect the declaration and overload signature before
recommending a change. Report-only rows do not establish the current ownership map.
