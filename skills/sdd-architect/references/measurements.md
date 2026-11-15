# Measurement meanings and filters

The `collect` command completes the arithmetic before substantive analysis. Values select questions; source investigation
establishes whether there is a problem. The script outputs measurements and
signals, not an architecture score or a refactoring verdict.
Obtain all numeric policy values through the [policy command](analysis-policy.md).
The names below refer to its resolved output; they do not prescribe defaults.

## JSONL catalog and record addressing

The executable catalog is [scripts/measurements.py](../scripts/measurements.py).
Adapters live in `inputs.py` and `history.py`; `analysis.py` joins normalized inputs
and emits the catalog; `graph.py` calculates graph definitions. `collection.py`
handles commands and storage. Each input is parsed once per collection.

Every `metrics/<name>/<level>.jsonl` is UTF-8: one independent JSON object per
nonempty line, never an array. Each row has exactly one measurement plus its key,
source location, supporting counters and completeness information. Source paths
are repository-relative with `/`. Shared formulas/units live here and in the
catalog; parameters and per-output availability live in `collection.json`.

In the tables, each comma-separated name and each listed level expands to its
own file. `G` expands to `class`, `package`, `module`; `S` to `file`, `package`,
`module`. Keys are complete JSON objects containing the listed fields. Rows sort
ascending by the canonical JSON of their key (keys sorted, Unicode preserved).
Member arrays sort lexically; dependency-layer `position` preserves peeling order.
A compound key retains the whole region and declaration, not a line number in a
JSONL file. `declaration` means the declaration reported by the instrument, which
can be a class, object, file or another scope; do not relabel it as a function.

| Primary name | Level | Key | Source, unit and measured population |
| --- | --- | --- | --- |
| `source-files` | file | file | Selected current Kotlin/Java files; package/language reference only |
| `class-files` | class | class | JVM SourceFile plus package or explicit override; file correspondence |
| `type-count`, `abstract-type-count` | file | file | Counts from the Kotlin declaration heuristic; Java values unknown; explicit abstract classes/interfaces only for the second count |
| `dependencies` | class | from, to | Unique directed admitted class pairs, value 1; nested classes retained |
| `changes` | commit | commit | Historical event: date, full changeset size, list of file numstat counters and binary flags; ID addresses the event only |
| `code-lines`, `total-lines` | file | file | scc Code and Lines respectively, in lines; whole reported file population within selected sources |
| `cyclomatic-complexity`, `cognitive-complexity` | function | file, region, declaration | detekt measured complexity at its actual function/method location |
| `method-length` | function | file, region, declaration | detekt LongMethod measured lines |
| `function-count` | declaration | file, region, declaration | detekt TooManyFunctions count at the declaration it reports |
| `parameter-list` | declaration | file, region, declaration | Count from the complete LongParameterList declaration; unsupported or ambiguous syntax stays unknown |
| `line-coverage`, `branch-coverage` | file | file | Separate covered/total counters and fraction; file population and mapping from the coverage source |

Retain raw finding pointers, region, declaration text, suppressions and unknown
numeric values. The raw pointer addresses the tool report; all links between
normalized measurements use object keys. Absence of a detekt finding is unknown,
including when `complete_mcc` was requested. Full-population claims require observed
MCC and no unknown or suppressed MCC findings for that file.

| Derived name | Level | Key | Dependencies, formula/unit and applicability |
| --- | --- | --- | --- |
| `dependencies` | package, module | from, to | Class edges; summed unique class-pair weights across the boundary |
| `node-count`, `edge-count` | G | graph | Corresponding graph; endpoint count and unique directed edge count |
| `fan-in`, `fan-out` | G | node | Corresponding graph; distinct direct consumers/suppliers, count |
| `incoming-weight`, `outgoing-weight` | G | node | Corresponding graph; sums of class-pair weights |
| `reachable-in`, `reachable-out` | G | node | Corresponding graph; reachable consumers/suppliers including self, count |
| `visibility-in`, `visibility-out` | G | node | Corresponding reachability / N, fraction; numerator and denominator retained |
| `propagation-cost` | G | graph | Sum reachable-out / N², fraction; N=0 is not applicable |
| `cyclic-components` | G | members | Corresponding graph; SCC member sets of size >1 |
| `cyclic-edges` | G | from, to | Edges inside cyclic components, class-pair weight |
| `dependency-layers` | G | members | Corresponding graph; peeling rule below, with kind and sequence position |
| `cohesion` | module | module | Package edges and declared map; internal/(internal+boundary), fraction; no weight is not applicable |
| `external-affinity` | package | package | Package edges and declared map; external module shares, denominator and unknown-ownership fraction; labels below |
| `ca`, `ce` | package | package | Package edges and type counts; incoming/outgoing class-pair weights; T meets `measurements.martin.minimum_types` and Ca+Ce>0 |
| `instability`, `abstractness`, `distance` | package | package | Martin I, A, D formulas below; same eligibility, partial type populations remain limited |
| `change-frequency` | S | level name | History: file commit count; package/module sum of current member-file counts, commits |
| `added-lines`, `deleted-lines`, `churn` | S | level name | History: additions, deletions, sum of both; groups sum current members; binary count retained |
| `activity`, `recent-activity` | package, module | level name | History and current membership; distinct commits for entire window / configured recent-day window, inclusive |
| `coupling` | file-pair | left, right | History; floor(200×shared/(rA+rB)), percent; configured changeset-size filter before both frequencies and shared support; all observed pairs retained |
| `implicit-coupling` | file-pair | left, right | Co-change, static edges and mapping; live Kotlin files in different packages without an observed direct edge; incomplete mapping limits the claim |
| `cyclomatic-complexity` | file | file | Sum observed unsuppressed function MCC, complexity; observed count and population completeness retained |
| `line-coverage`, `branch-coverage` | package, module | level name | Current membership and file coverage; sum covered/sum total, fraction; included/omitted/not-applicable files retained |
| `crap-file` | file | file | Observed file MCC and line coverage; CRAP_file formula below, adapted CRAP units |
| `crap-sum`, `crap-mean`, `crap-above-threshold` | package, module | level name | Defined file CRAP: sum, mean, count above `signals.crap.minimum_value`; explicit included/omitted/incomplete files; no measured values remains unknown |
| `hotspot-in-frequency`, `hotspot-out-frequency`, `hotspot-in-churn` | file | file | Mapped class visibility and history; max(V_in)×r, max(V_out)×r, max(V_in)×churn; weighted commits or lines respectively |
| `changes-per-code` | file | file | History and scc Code; `code_line_unit×r/Code`; Kotlin, configured minimum frequency and Code; settings in `measurements.changes_per_code` |

For scalar file outputs, the row universe is the union of current sources, admitted
report paths and paths observed in history. Missing observations get `value: null`
and `status: unknown` with a reason. Historical-only paths carry `live_production`
in frequency/churn rows and do not enter current package/module aggregates.
Group members come from current source packages and declared module ownership;
empty declared modules are retained. Full changesets remain in `changes/commit`
so filtering history cannot silently change coupling denominators.

### Outcomes, empty sets and references

`collection.json` contains `parameters`, resolved `analysis_policy`, raw artifact provenance, `outputs`, selection
links and gaps, without metric tables. Every output descriptor has path, record count
and one outcome: `complete`, `unavailable`, `error`, or `incomplete`. The last means
calculation has not finished; a successful empty file has `complete` and count 0.
A branch with unavailable inputs can retain unknown rows for known objects while
its output outcome still explains why no measurement was obtained.

Within a row, `measured` includes zero; `unknown` means missing information;
`not_applicable` means the formula's population/denominator condition is false;
`measured_subset` preserves a numeric result whose population is incomplete.
Coverage with total=0 is not applicable. If a group also omits files, its empty
measured denominator cannot establish applicability for the whole group.

Cite a metric using its path and full key, for example:

```json
{"path":"metrics/line-coverage/file.jsonl","key":{"file":"src/Order.kt"},"finding":"Coverage observation for the pricing scenario"}
```

`selections/rankings.jsonl` retains path, key, position and sorting condition for
non-null numeric unsuppressed observations. Ties sort by object key.
`selections/signals.jsonl` retains conditions and keyed references for cycles,
complexity/shape thresholds, supported co-change, hotspots, coverage and CRAP.
It records suitability and ordinal weights without copying metric values. Signals
have collection-local IDs and feed deterministic [candidate groups and the investigation queue](candidate-groups.md).
Selections do not establish a diagnosis. The `rank` command validates authored
recommendations after source analysis and resolves only the cited metric files.

### Treatment of prior auxiliary outputs

Comments, blank lines, scc Complexity and author identities remain in raw reports;
no normalized metrics, ownership shares or author/changeset summary scores are
emitted for them. History window and import parameters stay in artifact provenance;
actual event dates remain in `changes/commit`. Group file occurrences are represented
by summed `change-frequency`; distinct commits use `activity`. Former absent-path
lists are recoverable from historical events and `live_production`. Mapping gaps
live once in the collection description. Group coverage and three CRAP aggregates
are separate outputs with explicit membership. No auxiliary monolithic export is
retained.

## Graph and declared modules

`a → b` means a depends on b. Class edges are unique. Package/module edge weight
counts unique class pairs crossing that boundary, not calls or runtime frequency.
The class, package and declared-module graphs are different populations.
Nodes are edge endpoints; isolated declarations and internal edges discarded by
aggregation do not enter the corresponding denominator. Retain that scope when
comparing measurements. JVM nested classes are preserved in this implementation;
the pilot collapsed them, so those graph series are not directly comparable.

| View | Calculation and limit |
| --- | --- |
| SCC | Maximal mutually reachable set; cyclic groups have more than one member. A package SCC does not establish a class cycle. |
| Fan-in / fan-out | Distinct immediate consumers / suppliers; weighted totals are separate. |
| Visibility in / out | Reachable consumers / suppliers, including the node itself, divided by N. |
| Propagation cost | Reachable ordered pairs including the diagonal / N²; undefined for N=0. It measures neither regression probability nor the work or tokens needed for a change. |
| Layers | Peel nodes without suppliers; if none, without consumers; otherwise the largest SCC. Layer count has no better/worse direction. |
| Cohesion | Internal inter-package edge weight / (internal + incoming and outgoing boundary weight). Internal edges count once. Same-package class edges are absent. |
| External affinity | Package's incoming+outgoing weight to each other declared module / weight to all other declared modules. Own-module links are excluded. |
| I / A / D | `I=Ce/(Ca+Ce)`, `A=explicit abstract or interface declarations / type declarations`, `D=abs(A+I-1)`. Ca/Ce count weighted class pairs; require `measurements.martin.minimum_types` and Ca+Ce>0. Type counts are a source heuristic, not Kotlin semantic analysis. |

Unknown packages are not combined into a real module. The declared-module graph
excludes their edges; inspect package/class graphs and the map before asserting
independence. Cohesion reports all declared modules, including zero internal
weight and undefined denominators; unlike the pilot, missing rows are not hidden.

External affinity uses `measurements.external_affinity`: declared external fraction
below `minimum_declared_fraction` is grey; otherwise maximum share below
`minimum_leading_share` is orphan, second share at least `minimum_bridge_share` is
bridge, else leading external module. These labels select code to read, not a
destination for a package move.

A stable shared type can legitimately have high visibility, A=0 and D near 1.
An adapter can legitimately have low cohesion. Verify responsibility and a
representative change before prescribing an interface or moving a package.
Do not generate a greedy edge-removal count as a refactoring plan: graph deletions
neither establish a valid code transformation nor a minimum number of inversions.

## History and size

History uses commits in the recorded window, excluding merges. Per-file revisions
count commits; group activity counts distinct commits touching the group, not the
sum of file frequencies. Recent activity uses an inclusive window from the latest
log date minus `measurements.history.recent_days`. It is a nested window, not a
measured acceleration.

`churn = added + deleted` is rewritten text, not size growth. Binary changes retain
an explicit count; they do not become textual churn. Authors remain in the raw history for optional source investigation; authorship
aggregates are excluded from the measurement catalog.

For coupling, filter changesets larger than
`measurements.history.maximum_changeset_size` **before** computing both individual
frequencies and shared support. Retain every observed pair in JSONL. Selection
requires the minimum average frequency, shared commits and degree from
`signals.coupling`. Preserve rA, rB and shared;
`ceil((rA+rB)/2)` is the export's average-revs, not shared support. A 50% pair
can have rA=10, rB=30, shared=10; it is not a directional probability.

Implicit coupling candidates are live production Kotlin files in different
packages, with registered coupling and no observed direct static file edge in
either direction. This does not exclude transitive dependencies. Incomplete
class mapping limits the absence claim even when co-change itself is usable.
Inspect substantive joint commits; mechanical changes and implementation/test
pairs need no new architectural boundary.

Use scc `Code` for `code_line_unit×revisions/Code`, requiring Kotlin files and the
minimum frequency/size from `measurements.changes_per_code`. Retain the resolved
unit when comparing values. Current size and historical revisions have different time bases.
Do not use scc Complexity or warning counts as detekt complexity.

File structural hotspots use the **maximum** visibility among mapped classes:
`H_in_revisions=max(V_in)×r`, `H_in_churn=max(V_in)×churn`,
`H_out_revisions=max(V_out)×r`. They are neither unions of reachability nor
interchangeable units. Use `signals.hotspot.top_count` and its strict
`minimum_score` cutoff for each ranking; merge repeated files. The additional
frequency/visibility filter uses inclusive `minimum_frequency` and
`minimum_visibility` from the same group. All mapping limitations travel with the result.

## Complexity and coverage

Extract measured values from detekt messages for CyclomaticComplexMethod,
CognitiveComplexMethod, LongMethod and TooManyFunctions. For LongParameterList,
the adapter counts the complete declaration in the supported message, accounting
for nested syntax. Unknown/ambiguous declarations remain gaps. The analyzer's
`signals.shape.parameter_list_minimum` is separate from the detector's low
collection threshold. See [parameter counts](analysis-policy.md#parameter-counts-and-collection-thresholds).
Resolve overload signatures in code.

Absence of a finding is not measured zero. Suppressions/baselines/exclusions and
thresholds constrain the population. No system median or percentile is inferred
from a thresholded series. Full MCC coverage must be established separately.

Coverage is covered/total counters for lines and branches. Group coverage is
sum(covered)/sum(total), not the mean of percentages. A zero denominator is
not applicable; a missing report/counter is unknown. JaCoCo branch counters do
not count exception handlers; executing a line does not prove its assertion quality.

`CRAP_file = observed_MCC_sum^complexity_exponent × (1−line_coverage)^uncovered_exponent + observed_MCC_sum`,
with exponents from `measurements.crap`.
Missing coverage or MCC leaves it unknown. Incomplete MCC limits interpretation.
This is a file adaptation, not the original method metric: splitting files can
lower the aggregate without changing logic. Group sum/mean includes only listed
files; report the membership and omissions. `signals.crap.minimum_value` is a
strict reading filter, not a validated risk threshold for this adaptation.

## First-pass filters and evidence weights

All names in this table are under `signals`. Minimums are inclusive except the
explicitly strict hotspot score and CRAP comparisons; coverage's maximum is strict.

| Signal | Filter | Weight key under `evidence.weights` |
| --- | --- | --- |
| Cycle | SCC members ≥ `cycle.minimum_members` | `cycle` |
| Complexity | MCC ≥ `complexity.cyclomatic_minimum` or cognitive complexity ≥ `complexity.cognitive_minimum` | `complexity` |
| Shape | Lines ≥ `shape.method_length_minimum`, functions ≥ `shape.function_count_minimum`, or parameters ≥ `shape.parameter_list_minimum` | `shape` |
| Boundary | Martin D ≥ `boundary.distance_minimum` | `boundary` |
| Coupling | Degree, average frequency and shared commits meet the corresponding `coupling.minimum_*` values | `coupling` |
| Hotspot | Ranking within `hotspot.top_count` and score > `hotspot.minimum_score`; or frequency/visibility meet their minima | `hotspot` |
| Coverage | Frequency ≥ `coverage.minimum_frequency` and line coverage < `coverage.maximum_line_coverage` | `coverage` |
| CRAP | File value > `crap.minimum_value` | `crap` |

Fan-in/out, visibility, PC, layers, cohesion, affinity, churn and size remain
supporting views. They do not independently emit threshold signals or acquire
weights from an extra documentation matrix.

Diagnostic weights express relative attention to each goal; zero means no evidence
for that goal. Usable evidence retains its configured weight; limited evidence
is capped by `evidence.limited_weight_cap`; unusable evidence is excluded without
replacing its measurement by zero.
`evidence_weights` names these roles by `modularity`, `regression_risk` and
`change_cost_reduction`. Weights are ordinal and never added. Shared provenance
prevents double counting. A larger configured weight does not create evidence:
this metric set contains no measurements of agent tokens, human effort or end-to-end change time.
The queue sums capped evidence-family contributions under its separate policy;
`rank` sums grounded effect preference points after diagnosis. Neither sum uses
the diagnostic weights.

Use the [computed groups and queue](candidate-groups.md) for preliminary selection.
That contract defines exact-scope grouping, contained signals, overlaps, ordering,
budget and architect adjustments. Numeric rankings remain available for supporting
views; they are not an additional group-ranking algorithm.

Send selected source-available groups to [focused diagnosis](diagnosis.md).
Signals guide where to look; the source mechanism and feasible change
determine whether a recommendation is justified. Report the inspected scope
rather than treating the selected groups as a complete architecture assessment.

Keep the catalog bounded: no added nesting, duplication, mutation, diff coverage,
build-duration, Decoupling Level or architecture-rule-count metrics. Source review
and ArchUnit acceptance can explain/check a recommendation without adding a metric.
