# Preliminary candidate groups and investigation queue

`collect` prepares these selections after measurements and signal filters, through
[candidate_groups.py](../scripts/candidate_groups.py). The calculation is pure:
it reads normalized rows and declared package ownership, with no additional tools,
source copies or source-version checks. Equal inputs and parameters produce equal
groups and ordering regardless of input iteration order.

Read these outputs before the first architect shortlist. They bound the initial
source investigation; they do not establish a common cause, readiness or expected
M/R/S effects. Recommendation priority still belongs to `rank` after diagnosis.

## Inputs and addressing

The existing [signal filters](measurements.md#first-pass-filters-and-evidence-weights)
remain the starting population. They include unsuppressed `LongParameterList`
findings even when their numeric count is unknown, and Martin distance at least
0.7 as supporting context. No numeric zero is invented for an unknown count.

Exact duplicate signals are removed. Each signal has a collection-local `signal`
ID assigned after canonical sorting of its family, condition, keyed references,
suitability and ordinal weights. It is addressed by
`{"path":"selections/signals.jsonl","key":{"signal":"signal-0001"}}`.
These IDs address retained records only; they are not durable source identities.

`candidate_group_limit` in project configuration is a positive integer, default
12. The resolved value is retained in `collection.json.parameters`. It limits
automatic selection, not the number of groups retained or an architect's justified
adjustment. Fewer available groups need no artificial additions to reach eight.

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
| `category`, `ordering_signal` | Investigation category and seed used for ordering |
| `source_available`, `limitations` | Current source availability and evidence/mapping gaps |

No metric values are copied into groups. Multiple transformations of one input
remain related evidence; neither signal counts nor M/R/S weights are summed.
Source availability does not establish diagnosis quality or implementation readiness.

## Order and select

Give each group the earliest position supported by one of its seed signals under
the following comparison. Attached context does not change its category.

1. Category: structural, then risk, then supporting.
2. Within a category: usable evidence before limited evidence.
3. Within that suitability: the rule order below.
4. Within a rule: measurement identifier lexically, then its numeric value descending.
   Coverage uses its fraction ascending; cycles use member count descending. Unknown
   counts follow measured values of the same metric and tie by key, without an
   invented measurement.
5. Break remaining ties by the canonical signal ID, then group ID.

| Category | Rule order |
| --- | --- |
| Structural | Cycles; co-change at least 60%; hotspots; remaining supported co-change |
| Risk | Function complexity; low coverage with change activity; file CRAP |
| Supporting | Declaration shape, including parameter findings; Martin distance |

Values from different measurements are never compared as a common severity score.
The category policy can exhaust the budget on structural groups; retained deferred
risk/supporting groups make that limitation visible for the architect to assess.

Walk this ordering once. Select a group when its seed signals are not all already
included in selected groups and the budget has room. Mark a group covered when
all its seeds are already included; record the selected covering group IDs.
Otherwise mark it deferred by the budget. Every group gets a row in
`selections/investigation-queue.jsonl`, including covered and deferred groups:

| Field | Meaning |
| --- | --- |
| `candidate_group` | JSONL path and full `{"group":"group-0001"}` key |
| `position` | Position in the complete ordered queue |
| `category`, `ordering_signal` | Explain the deterministic ordering |
| `selected` | Whether this group consumes an automatic investigation slot |
| `reason`, `covered_by` | Selection, budget deferral or coverage by selected groups |

An empty calculated queue is complete. Missing upstream measurements remain gaps
in the collection; an interrupted grouping remains incomplete like other selections.

## Architect handoff

Start from selected queue entries and inspect their groups, overlaps, limits and
the deferred population. Save the final shortlist in `diagnosis.md`, linking each
computed origin by path/key and explaining each merge, split, addition or omission.
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
