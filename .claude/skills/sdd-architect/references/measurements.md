# Measurement meanings and filters

Use `analyze` for the arithmetic. Values select questions; source investigation
establishes whether there is a problem. The script outputs measurements and
signals, not an architecture score or a refactoring verdict.

## Graph and declared modules

`a → b` means a depends on b. Class edges are unique. Package/module edge weight
counts unique class pairs crossing that boundary, not calls or runtime frequency.
The class, package and declared-module graphs are different populations.
Nodes are edge endpoints; isolated declarations and internal edges discarded by
aggregation do not enter the corresponding denominator. Retain that scope when
comparing snapshots. JVM nested classes are preserved in this implementation;
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
an explicit count; they do not become textual churn. Author counts and top-author
share provide context with weight zero; they do not measure quality or bus factor.

For coupling, filter changesets larger than 30 files **before** computing both
individual frequencies and shared support. Then require mean frequency ≥5,
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
co-change deserve early investigation; an important cold candidate remains eligible.
Merge SCC, visibility and hotspot signals for the same area. Near a boundary
(29/30%, 9/10 revisions), inspect the neighboring case instead of inventing a
health cliff. Explain shortlist omissions as budget limits, not absence of problems.

Keep the catalog bounded: no added nesting, duplication, mutation, diff coverage,
build-duration, Decoupling Level or architecture-rule-count metrics. Source review
and ArchUnit acceptance can explain/check a recommendation without adding a metric.
