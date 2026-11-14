# Measurement meanings and filters

The `collect` command completes the arithmetic before substantive analysis. Values select questions; source investigation
establishes whether there is a problem. The script outputs measurements and
signals, not an architecture score or a refactoring verdict.

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
| `parameter-list` | declaration | file, region, declaration | LongParameterList finding; parameter count stays unknown when absent from the message |
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
| `ca`, `ce` | package | package | Package edges and type counts; incoming/outgoing class-pair weights; T≥5 and Ca+Ce>0 |
| `instability`, `abstractness`, `distance` | package | package | Martin I, A, D formulas below; same eligibility, partial type populations remain limited |
| `change-frequency` | S | level name | History: file commit count; package/module sum of current member-file counts, commits |
| `added-lines`, `deleted-lines`, `churn` | S | level name | History: additions, deletions, sum of both; groups sum current members; binary count retained |
| `activity`, `recent-activity` | package, module | level name | History and current membership; distinct commits for entire window / last 30 days, inclusive |
| `coupling` | file-pair | left, right | History; floor(200×shared/(rA+rB)), percent; changesets ≤30 before both frequencies and shared support; all observed pairs retained |
| `implicit-coupling` | file-pair | left, right | Co-change, static edges and mapping; live Kotlin files in different packages without an observed direct edge; incomplete mapping limits the claim |
| `cyclomatic-complexity` | file | file | Sum observed unsuppressed function MCC, complexity; observed count and population completeness retained |
| `line-coverage`, `branch-coverage` | package, module | level name | Current membership and file coverage; sum covered/sum total, fraction; included/omitted/not-applicable files retained |
| `crap-file` | file | file | Observed file MCC and line coverage; CRAP_file formula below, adapted CRAP units |
| `crap-sum`, `crap-mean`, `crap-above-threshold` | package, module | level name | Defined file CRAP: sum, mean, count >30; explicit included/omitted/incomplete files; no measured values remains unknown |
| `hotspot-in-frequency`, `hotspot-out-frequency`, `hotspot-in-churn` | file | file | Mapped class visibility and history; max(V_in)×r, max(V_out)×r, max(V_in)×churn; weighted commits or lines respectively |
| `changes-per-code` | file | file | History and scc Code; 100×r/Code, commits per 100 code lines; Kotlin, r≥5 and Code≥20 |

For scalar file outputs, the row universe is the union of current sources, admitted
report paths and paths observed in history. Missing observations get `value: null`
and `status: unknown` with a reason. Historical-only paths carry `live_production`
in frequency/churn rows and do not enter current package/module aggregates.
Group members come from current source packages and declared module ownership;
empty declared modules are retained. Full changesets remain in `changes/commit`
so filtering history cannot silently change coupling denominators.

### Outcomes, empty sets and references

`collection.json` contains `parameters`, raw artifact provenance, `outputs`, selection
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
It records suitability and ordinal weights without copying metric values.
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
| Propagation cost | Reachable ordered pairs including the diagonal / N²; undefined for N=0. It is neither regression probability nor development speed. |
| Layers | Peel nodes without suppliers; if none, without consumers; otherwise the largest SCC. Layer count has no better/worse direction. |
| Cohesion | Internal inter-package edge weight / (internal + incoming and outgoing boundary weight). Internal edges count once. Same-package class edges are absent. |
| External affinity | Package's incoming+outgoing weight to each other declared module / weight to all other declared modules. Own-module links are excluded. |
| I / A / D | `I=Ce/(Ca+Ce)`, `A=explicit abstract or interface declarations / type declarations`, `D=abs(A+I-1)`. Ca/Ce count weighted class pairs; show only T≥5 and Ca+Ce>0. Type counts are a source heuristic, not Kotlin semantic analysis. |

Unknown packages are not combined into a real module. The declared-module graph
excludes their edges; inspect package/class graphs and the map before asserting
independence. Cohesion reports all declared modules, including zero internal
weight and undefined denominators; unlike the pilot, missing rows are not hidden.

External affinity labels retain the pilot rules: declared external fraction <.34
is grey; otherwise maximum share <.25 is orphan, second share ≥.33 is bridge,
else leading external module. There is no applied 50% dominance rule. These
labels select code to read, not a destination for a package move.

A stable shared type can legitimately have high visibility, A=0 and D near 1.
An adapter can legitimately have low cohesion. Verify responsibility and a
representative change before prescribing an interface or moving a package.
Do not generate a greedy edge-removal count as a refactoring plan: graph deletions
neither establish a valid code transformation nor a minimum number of inversions.

## History and size

History uses commits in the recorded window, excluding merges. Per-file revisions
count commits; group activity counts distinct commits touching the group, not the
sum of file frequencies. The 30-day view is inclusive from latest log date minus
30 days. It is a nested window, not a measured acceleration.

`churn = added + deleted` is rewritten text, not size growth. Binary changes retain
an explicit count; they do not become textual churn. Authors remain in the raw history for optional source investigation; authorship
aggregates are excluded from the measurement catalog.

For coupling, filter changesets larger than 30 files **before** computing both
individual frequencies and shared support. Retain every observed pair in JSONL. Selections require mean frequency ≥5,
shared commits ≥5 and `floor(200×shared/(rA+rB)) ≥30`. Preserve rA, rB and shared;
`ceil((rA+rB)/2)` is the export's average-revs, not shared support. A 50% pair
can have rA=10, rB=30, shared=10; it is not a directional probability.

Implicit coupling candidates are live production Kotlin files in different
packages, with registered coupling and no observed direct static file edge in
either direction. This does not exclude transitive dependencies. Incomplete
class mapping limits the absence claim even when co-change itself is usable.
Inspect substantive joint commits; mechanical changes and implementation/test
pairs need no new architectural boundary.

Use scc `Code` for `100×revisions/Code`, requiring Kotlin files, revisions≥5 and
Code≥20. Current size and historical revisions have different time bases.
Do not use scc Complexity or warning counts as detekt complexity.

File structural hotspots use the **maximum** visibility among mapped classes:
`H_in_revisions=max(V_in)×r`, `H_in_churn=max(V_in)×churn`,
`H_out_revisions=max(V_out)×r`. They are neither unions of reachability nor
interchangeable units. Review the top five of each, merge repeated files, and
also flag r≥10 with V_in≥.05. All mapping limitations travel with the result.

## Complexity and coverage

Extract measured values from detekt messages for CyclomaticComplexMethod,
CognitiveComplexMethod, LongMethod and TooManyFunctions. LongParameterList
in the pilot contains the signature and threshold but no measured count:
leave its number unknown and inspect the declaration. Splitting on commas
would miscount generic and functional types. Resolve overload signatures in code.

Absence of a finding is not measured zero. Suppressions/baselines/exclusions and
thresholds constrain the population. No system median or percentile is inferred
from a thresholded series. Full MCC coverage must be established separately.

Coverage is covered/total counters for lines and branches. Group coverage is
sum(covered)/sum(total), not the mean of percentages. A zero denominator is
not applicable; a missing report/counter is unknown. JaCoCo branch counters do
not count exception handlers; executing a line does not prove its assertion quality.

`CRAP_file = observed_MCC_sum² × (1−line_coverage)³ + observed_MCC_sum`.
Missing coverage or MCC leaves it unknown. Incomplete MCC limits interpretation.
This is a file adaptation, not the original method metric: splitting files can
lower the aggregate without changing logic. Group sum/mean includes only listed
files; report the membership and omissions. The >30 filter is not a validated
risk threshold for this adaptation.

## First-pass filters and evidence weights

| Signal/filter | M | R | S |
| --- | --- | --- | --- |
| SCC >1 member | 2 | 1 | 1 |
| Fan-in/out, visibility, PC individually | 1 | 1 | 0 |
| Layers; cohesion, affinity, I/A/D (D≥.7 as a reading cue) | 1 | 0 | 0 |
| Cross-boundary coupling (30/5/5; start with ≥60%) | 2 | 1 | 1 |
| Structural hotspots | 2 | 1 | 1 |
| Revisions, churn, revisions per 100 Code | 1 | 1 | 1 |
| Function MCC≥10 or cognitive complexity≥15 | 1 | 2 | 1 |
| LongMethod≥20, TooManyFunctions>10, selected parameter finding | 1 | 1 | 1 |
| Code/Lines size | 1 | 0 | 1 |
| Coverage (r≥13 and line coverage<.5); CRAP_file>30 | 0 | 2 | 0 |
| Authors, comments, blank lines, summary, absent paths | 0 | 0 | 0 |

2 means a primary diagnostic signal, 1 supporting context, 0 no evidence for
that goal. Usable evidence retains the matrix weight; limited evidence is capped
at 1; unusable evidence is excluded without replacing its value by zero.
Weights are ordinal and never added. Shared provenance prevents double counting.
All speed weights are ≤1 because this metric set contains no speed measurements.

Start with 8–12 groups: structural candidates, then risk, then supporting views
that could change a diagnosis. New/changed cycles and graph plus substantive
co-change deserve early investigation. Include candidates justified by a known
incident, critical contract or upcoming change even without historical activity.
Unknown or absent history is not evidence of safety. A hotspot's cause can be in
a cold dependency, which remains eligible for the same scoped investigation.
Merge SCC, visibility and hotspot signals for the same area. Near a boundary
(29/30%, 9/10 revisions), inspect the neighboring case instead of inventing a
health cliff. Explain shortlist omissions as budget limits, not absence of problems.

Send selected source-available groups to [focused diagnosis](diagnosis.md).
Signals guide where to look; the source mechanism and feasible change
determine whether a recommendation is justified. Report the inspected scope
rather than treating the selected groups as a complete architecture assessment.

Keep the catalog bounded: no added nesting, duplication, mutation, diff coverage,
build-duration, Decoupling Level or architecture-rule-count metrics. Source review
and ArchUnit acceptance can explain/check a recommendation without adding a metric.
