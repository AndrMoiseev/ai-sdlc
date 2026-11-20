# Project and module quality indicators

This is the full-audit aggregate contract. Resolve numerical parameters through
`metrics.py policy`, group `measurements.quality_indicators`. The scripts calculate
these values separately from recommendation priority points and the keyed JSONL
diagnostic catalog. They do not establish a diagnosis or measured future benefit.

## Population and prerequisites

Use every production `.kt` file in the configured source inventory after exclusions.
Retain isolated files. JVM classes map through SourceFile/package or explicit
verified correspondences. Each Kotlin package has exactly one architectural module
under longest-prefix ownership. Gradle projects define build scope, not modules.
Java files remain visible in repository statistics and the diagnostic catalog;
the first aggregate quality profile measures Kotlin/JVM only.

Full collection requires all six sources: jdeps dependencies, complete rename-aware
Git history for the policy window, repository-wide scc per-file data, complete
Kotlin token/function measurements, detekt SARIF and merged JaCoCo XML from passed
selected tests. Failure, unconfigured coverage, unresolved mapping or missing
required counters stops the audit. Tell the user what to resolve before restarting.
Do not turn unavailable inputs into zero, a reduced denominator or a partial Q.
An actually empty denominator is `not_applicable`, encoded as null with its counters.

Kotlin measurements use the existing detekt runtime's lexer, PSI and cognitive
complexity through the bundled plugin. The JSON schema and measurement profile
are declared in [plugins.json](../bin/plugins.json), separately from the runtime.
Retain actual detekt, Kotlin parser and plugin versions: changing the host can
change tokenization or complexity results, so inspect those versions when comparing
audits. The project task supplies the report from its configured adapter.
The plugin rejects syntax errors. It does not infer dependencies from imports
or substitute its parser for jdeps. Syntax compatibility must hold for the actual
project; a construct unsupported by that project's detekt is a prerequisite failure.

Code tokens exclude whitespace, comments and package/import directives. Token type,
identifier and literal spelling remain intact. Positions are UTF-16 offsets after
LF normalization and optional UTF-8 BOM removal when accepted by the host parser.
The plugin does not reparse or repair sources rejected by detekt. Named functions with bodies carry
signature, owner, cognitive complexity and nesting. Classes/objects and function
bodies supply size containers. Suppressions and detector warning thresholds do not
remove functions from these aggregate measurements.

## Structural separability D

Project admitted class edges onto source files, deduplicate directed file pairs
and remove self-edges. The Kotlin graph includes all inventory files, including
isolates. `a -> b` means consumer a depends on supplier b. Bytecode lowering,
inline functions, reflection and DI limit what jdeps exposes; record that model
limitation without pretending to recover semantic Kotlin relationships.

The builder implements the three steps of ArchDRH-Re (§4 of the
[author's paper](https://www.cs.drexel.edu/~yc349/papers/2013/QoSA2013.pdf)):

1. Condense SCCs. Find terminal consumers, traverse their suppliers and label each
   node by the terminal-consumer set that reaches it. Connected regions with the
   same label form groups. SCC members remain together.
2. Assign layers by longest supplier path, with supplier roots at layer 1. Merge
   groups in the same layer with identical nonempty immediate supplier-group sets.
   Independent root groups remain separate.
3. Recurse into groups unless `E < V` or `E > V^1.5`. Detach condensed components
   with no consumers as control groups; repeat the first two steps on the remainder.
   A single SCC cannot be split by this method and terminates recursion.

Flatten only terminal groups, then assign layers once across the full group graph.
Put isolated files in separate singleton groups at the final layer. Lexical file
ordering resolves traversal ties. Every file appears exactly once; distinct groups
in a layer have no edges between them. These flattening and isolate conventions
belong to profile `kotlin-jvm-jdeps-archdrh-re-1`. Keep the convention explicit when
checking the implementation on real projects; a different builder starts a new profile.

For each non-final group M, let b be the number of files in all lower layers and d
the number of those files reaching any member of M. Its contribution is
`100 * |M| / N * (1 - d/b)`. Count the union of consumers, never a sum of paths.
For final-layer groups use `100 * |M| / N * g(|M|)`, where g is 1 up to
`small_group_files`, then `ln(small_group_files)/ln(|M|)`. D sums these contributions.
Retain groups, layers, b, d and contributions alongside the value.

The same complete file graph supplies N, edge count, SCC membership, cyclic-file
count/fraction, largest SCC size (one for a nonempty acyclic graph), incoming
visibility per file and PC. PC is
reachable ordered pairs including the diagonal divided by N squared. These values
explain D and do not receive additional weights in Q. The older class/package/module
catalog graphs use endpoint populations; their PC denominators are different.

## Local maintainability L and duplication U

Let W be all code tokens. For each named function not nested inside another named
function, w is its whole-body token count and C its cognitive complexity. Nested
bodies are included once through their containing function. With resolved threshold c:

```text
cognitive_excess = sum(w * max(0, C/c - 1))
C_score = 100 / (1 + cognitive_excess / sum(w))
```

For each token take the maximum positive size excess `size/container_limit - 1`
among its containing function bodies, classes/objects and file. Container limits
are `function_tokens`, `class_tokens`, `file_tokens`. Sum those per-token excesses:

```text
S_score = 100 / (1 + size_excess / W)
L = sqrt(C_score * S_score)
```

Retain function count/weight, tokens outside functions, maximum and token-weighted
p95 cognitive complexity, complex-function token count/fraction and the ten largest
cognitive and file-size contributions. No functions means C_score and L are
not applicable; a declaration-only population must not acquire a fabricated 100.

Find exact equal token sequences at least `clone_tokens` long. Sequences stay
within files; occurrences in the same file must not overlap. Count the union of
all participating positions, including the first occurrence. Hashes only select
candidates: full token sequences verify equality. Matching minimum-length windows
produce the same union as extended clones. Store intervals and counts per file.

```text
d = duplicated_tokens / W
U = 100 / (1 + d / duplication_reference)
Q = (D * L * U)^(1/3)
```

If a component is not applicable, Q is null. Never average available components or
change their weights. Preserve full precision in JSON; round only for Markdown.

## Coverage, CRAP_exec and history

Coverage uses summed covered/total branch and instruction counters from included
JVM methods, plus unique executable source lines from JaCoCo sourcefile records.
Require every mapped production Kotlin class in the merged report, even when
JaCoCo filters all of its methods. Every included executable method needs positive
instruction and COMPLEXITY totals; executable files need source-line data.
JaCoCo's [XML exporter](https://github.com/jacoco/jacoco/blob/master/org.jacoco.report/src/org/jacoco/report/internal/xml/XMLCoverageWriter.java)
omits zero-total counters, so absent BRANCH means zero branches only for this
qualified complete XML format. This rule does not apply to arbitrary missing data.

Identify a method by JVM class, name and descriptor. Let v be its JaCoCo COMPLEXITY
total. Use `c = min(instruction_fraction, branch_fraction)` when branches exist,
otherwise the instruction fraction. Calculate each method before aggregating:

```text
e = v^2 * (1 - c)^3
CRAP_exec = v + e
total_crap = sum(CRAP_exec)
total_excess = sum(e)
excess_density = 1000 * total_excess / W
E_CRAP = 100 * total_excess / sum(v^2)
```

Also retain method count, p95 CRAP_exec and the ten largest excesses. These values
do not enter Q. The diagnostic catalog's detekt/line-coverage file CRAP has a
different definition and must not supply these aggregates.

History covers `history_days` through the collection's UTC date, first-parent only,
without merge commits. Track Git-detected renames backwards to current paths.
Retain full changesets; exclude commits exceeding `history_maximum_files`
production Kotlin files before calculating both individual and joint frequencies.
For a,b use `2 * shared / (revisions_a + revisions_b)`; require the policy's shared,
average and coupling minima. Retain pairs and current token exposure to at least
one qualifying partner. Count observations touching the measured area and excluded
large commits. Too few observations yields `limited`, not evidence of independence.
A complete empty/short project history is valid; unavailable or truncated history
is a blocker. Historical IDs address events, not the audited source version.

## Project and architectural modules

Recalculate each module on its own files: induced dependency graph, local token
clones, function weights, method/line coverage and history partners. Do not average
module scores to obtain project scores. Retain empty declared modules with null
ratios rather than dropping them.

Alongside local metrics show incoming/outgoing boundary edges, member files in
cycles of the full project graph, tokens in cross-module clones, all project-clone
tokens belonging to the module, and token exposure to cross-module co-change.
This preserves problems that disappear when cutting the graph or clone population.

scc statistics cover its repository file population after documented exclusions.
Keep Files, Lines, Code, Comment and Blank totals, language totals and
production/tests/other totals. Every production source must appear in scc.
Production and test source packages determine module assignment; other repository
files remain in project statistics without fabricated architectural ownership.

## Publication

`collect` stores `metrics/quality-indicators.json` in the current audit only. It
contains schema version, time, profile/parameters, scope, tool provenance and raw
input paths relative to the audit, limitations, project results and module results.
No collection step writes or clears the live status.

After successful analysis, ranking, report and plan update, run the publication command:

```text
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" status --repository "<project-root>" --collection "<report-dir>/collection.json"
```

The command requires a complete full collection, calculated aggregates, report and
plan. It publishes `status.json`, template-rendered `status.md` and a verbatim copy
of `assets/status-indicators.md` together in `memory/tech-debt/`. JSON stores
unrounded numbers and denominators. The Markdown tables link each indicator to
its section in the companion guide. The command refreshes all three files on
each successful full audit. Focused work does not publish status. After the
publication result and handoff are verified, the orchestrator records completion
in `state.json` under the [workflow](workflow.md#phase-7-project-status-and-delivery).

Any earlier failure or interruption leaves the previous publication untouched. Prepare
serialization/rendering before writing, but use plain final writes: no backups,
transactions, rollback or special recovery. If the final write itself fails,
report the failure; earlier committed values are available in Git.
