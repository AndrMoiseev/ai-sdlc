# Execution state version 3

The executable format contract lives in `scripts/lib/state.py`,
`state_objects.py` and `state_history.py`; transition handlers enforce
event-specific invariants. These checks govern persisted execution state.

The runtime accepts only schema version 3. Preserve an old execution until an
explicit conversion has verified it and saved a backup; ordinary reads never
migrate or rewrite state. The input basis uses schema 2 with admission `head`.
Document paths are derived when needed; specification files and document contents
come from the current `HEAD` of `basis.project_root`.
Preserve legacy manifests and execution evidence for explicit
reconciliation; accepting a checkpoint alone cannot approve extra tasks.

## Current state and immutable objects

`state.json` is the atomic commit point. It holds run identity, revision,
task control fields, budgets and references. It contains no inline event
list. Task histories, current-change document snapshots, task transfer patches
and large values live under
`objects/<hash-prefix>/<sha256>.json`. Identical canonical JSON bytes share one
file. A reference records the relative path, SHA-256, byte length and JSON kind.
Paths must match their hashes and remain inside the execution directory.

The engine loads referenced fields on access. Copying state preserves unopened
references; saving serializes accessed/changed branches without opening the
others. Values over 4096 encoded bytes are externalized, as are designated source
document snapshots and history collections. Basis and task control mappings remain inline.
The manifest therefore does not embed source inventories or accumulated reports.
Keep large new runtime fields behind references; include a storage/read regression
when adding them. Generated dashboards are disposable projections.

## History and integrity

`event_head` identifies the last immutable event; each event links its predecessor.
`event_index` identifies an immutable trie keyed by the SHA-256 of event IDs. A
retry reads its index path and saved result instead of scanning earlier events.
Changed envelopes under the same ID fail. Both pointers are covered by manifest
integrity, along with its revision and current state.

Ordinary reads verify manifest integrity, root binding, status constraints, the
history head and every object they access. `audit` verifies all current referenced
objects and the complete event chain/index. It checks event identities, request
fingerprints, revisions and index membership. `resume` and `finalize` run this
audit before their transition. Historical corruption can remain undetected by a
status read; that read is not a complete-history audit. Hashes do not authenticate
against an actor able to rewrite the entire store.

Under the exclusive execution lock, write immutable objects and the new event/index
first, then atomically replace `state.json`. Only references reachable from the
committed manifest participate in transitions and retries. If replacement fails,
the previous revision stays valid; abandoned objects do not count as accepted
events. Retain external-effect intents so an interrupted Git operation can be
reconciled using its original event envelope. Do not delete objects during active
execution: archived runs and effects can retain references.

When replacing a plan, archive the manifest and link previous task results through
objects; do not hydrate and nest past attempts. Exclude the execution directory
from dirty-path lists, status and document snapshots, including
already tracked execution artifacts.

## Source identity

Use the local candidate commit SHA and clean Git state to identify source code.
Command logs capture that identity before and after tests; changes during a run make it stale.
The runtime takes file-content snapshots only inside the current SDD change or
refactoring directory, excluding its execution directory. It does not create
per-file source hashes or full working-copy inventories elsewhere. Cleanup uses
Git ownership and status checks and preserves unknown or ignored data.

Historical source snapshots stay readable as historical evidence. They do not
establish commit identity and cannot be reused for a new commit candidate. Keep
their objects intact and obtain fresh evidence through the supported workflow.

## Reading evidence

Use `read` with `view: "compact"` for control decisions and `view: "full"` to see
the manifest's references. Use `read_object` for one descriptor at a time. It
verifies the requested bytes and leaves nested references encoded. Reports retain their existing paths; their snapshot data may also
contain object references. Preserve the complete execution directory when moving
or backing up evidence; copying `state.json` alone is insufficient.

Task candidate artifacts and references are no longer written. Historical candidate files are left untouched and are not consulted by current checks or resume.
