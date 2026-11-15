# Preliminary candidate groups and investigation queue

`collect` prepares these selections after measurements and signal filters, through
[candidate_groups.py](../scripts/candidate_groups.py). The calculation is pure:
it reads normalized rows and declared package ownership, with no additional tools,
source copies or source-version checks. Equal inputs and parameters produce equal
groups and ordering regardless of input iteration order.

Read these outputs before the first architect shortlist. They bound the initial
source investigation; they do not establish a common cause, readiness or expected
M/R/C effects. Recommendation priority still belongs to `rank` after diagnosis.

## Inputs and addressing

The existing [signal filters](measurements.md#first-pass-filters-and-evidence-weights)
remain the starting population. They include measured, unsuppressed parameter lists
meeting the analyzer threshold and Martin distance meeting its configured threshold.
Unknown parameter counts remain measurement gaps, without numeric threshold selection.

Exact duplicate signals are removed. Each signal has a collection-local `signal`
ID assigned after canonical sorting of its family, condition, keyed references,
suitability and ordinal weights. It is addressed by
`{"path":"selections/signals.jsonl","key":{"signal":"signal-0001"}}`.
These IDs address retained records only; they are not durable source identities.

`investigation.candidate_group_limit` in the [analysis policy](analysis-policy.md)
sets the automatic budget. Obtain its actual value through `metrics.py policy`.
The resolved value is retained in `collection.json.analysis_policy`. It limits
automatic selection, not the number of groups retained or an architect's justified
adjustment. Fewer available groups need no artificial additions to fill the budget.

## Build groups

1. Recover each signal's source scope. A file or declaration finding supplies its
   file; co-change supplies its two files. A class cycle uses explicit/JVM source
   mapping. Package and declared-module cycles use current source membership.
   Preserve all original measurement references, including graph granularity.
2. Merge signals whose fully resolved file sets are exactly equal. This groups
   observations for an area, not confirmed causes. Different function findings in
   one file retain their complete declaration keys in their signal references.
3. Keep partial mappings explicit: retain known files, unresolved objects and
   original measurement keys. An equal known subset does not merge partial groups.
   Source-free file findings retain their paths and a missing-source limitation.
4. Attach signals whose entire resolved file set is contained in a group's file
   set as additional context. Preserve the group's original `seed_signals` separately
   from all attached `signals`. Partial mappings do not participate in containment.
5. Calculate pairwise shared files through an inverted file index. Retain these
   overlaps without merging groups or taking a transitive closure. Groups `{A,B}`
   and `{B,C}` therefore remain separate; no synthetic `{A,B,C}` group is created.

Each `selections/candidate-groups.jsonl` record contains:

| Field | Meaning |
| --- | --- |
| `group` | Collection-local ID, assigned by canonical scope order |
| `scope` | Sorted files; unresolved objects and measurement keys when mapping is partial |
| `seed_signals` | Keyed signal references that created this exact scope |
| `signals` | Deduplicated seed and contained signal references |
| `overlaps` | Other group IDs and their exact shared files |
| `evidence_families` | Each evidence family's capped points and keyed signal references |
| `investigation_score` | Sum of those family contributions, used for investigation ordering |
| `source_available`, `limitations` | Current source availability and evidence/mapping gaps |

No metric values are copied into groups. Multiple transformations of one input
remain related evidence; neither raw signal counts nor diagnostic evidence weights are summed.
Source availability does not establish diagnosis quality or implementation readiness.

## Order and select

Use seed and fully contained signals to calculate one capped contribution per
evidence family. Partial mappings retain only their own seed signals.

| Evidence family | Related signal families |
| --- | --- |
| `dependency_structure` | Cycles at all granularities; Martin distance |
| `change_patterns` | Co-change, including implicit co-change; all structural hotspots |
| `code_risk` | Function complexity; declaration shape; low coverage with change activity; file CRAP |

Each family contributes its configured `investigation.family_points.usable` when
any signal is usable, or `limited` when only limited signals are present. An absent family contributes no points and
supplies no evidence of safety. Record only present families, with their points
and all keyed signal references. Sum the capped contributions as
`investigation_score`. These are investigation preference
points; they are separate from the diagnostic evidence weights and recommendation
effects. The conservative families keep graph derivatives together, hotspots with
their change-history context, and CRAP with its complexity/coverage inputs.
They do not assert independent causes or statistical independence.

Order groups by descending score. Equal scores mean equal investigation priority;
canonical scope/group ID determines only reproducible display and budget selection.
There is no structural-before-risk rule or metric-magnitude tie-breaker. Multiple
functions, granularities, copies or derivatives in one family cannot inflate its
contribution; a larger file scope gains no points merely for its size. Distinct
families in one group raise its investigation priority without establishing a common
cause. Overlapping groups retain their own scopes and shared evidence references.

Walk this ordering once. Select a group when its seed signals are not all already
included in selected groups and the budget has room. Mark a group covered when
all its seeds are already included; record the selected covering group IDs.
Otherwise mark it deferred by the budget. Every group gets a row in
`selections/investigation-queue.jsonl`, including covered and deferred groups:

| Field | Meaning |
| --- | --- |
| `candidate_group` | JSONL path and full `{"group":"group-0001"}` key |
| `position` | Position in the complete ordered queue |
| `investigation_score`, `evidence_families` | Explain the score and its capped contributions |
| `selected` | Whether this group consumes an automatic investigation slot |
| `reason`, `covered_by` | Selection, budget deferral or coverage by selected groups |

An empty calculated queue is complete. Missing upstream measurements remain gaps
in the collection; an interrupted grouping remains incomplete like other selections.

## Architect handoff

Start from selected queue entries and inspect their groups, overlaps, limits and
the deferred population. Save the final shortlist in `diagnosis.md`, linking each
computed origin by path/key and explaining each merge, split, addition or omission.
Compare candidates with the [current tech debt plan](tech-debt-plan.md#read-the-plan-before-investigation).
Link matching existing tasks and reuse adequate diagnoses. Known tasks can reduce
the substantive investigation, but do not remove files or signals from collection.
Keep these calculations in `collect`; the architect does not reconstruct filters
or rerank raw measurements by hand.

Add critical contracts, incidents and upcoming changes from task context even when
they have no computed signal. Inspect neighboring threshold cases when their
scenario can change the diagnosis. Follow a cold dependency to the actual cause.
Expand or reduce the initial budget only with an explicit scope/cost explanation.
The final shortlist can contain fewer groups or none; unknown history is not safety.

Two signals with the same files may explain different mechanisms. Conversely,
overlapping groups may share a cause discovered only during source inspection.
Resolve that distinction in diagnosis and integration, preserving the original
computed records as evidence of how the investigation began.
