# Diff review and post-change reassessment

Use these [explicit focused routes](continuation.md#explicit-focused-routes)
within the four-phase contracts. The orchestrator maintains configuration on a
run with a checkout, registers exact comparison/acceptance checks, and records
the phase, basis and unresolved work in `state.md`. Explorers collect evidence;
architects diagnose and integrate it. Keep source changes outside this audit.

For a diff, fix base and target revisions and any working-tree state. Inspect
affected consumers even when they are outside the diff. Collect separate numbered
snapshots under comparable definitions and preserve the actual configuration and
source identity for each. Read a particular graph at its own level; a package
cycle is not a class cycle. Use the same package map unless the change explicitly
revises it. Keep earlier snapshots and raw results intact.

For source-available diff candidates or a reopened diagnosis, use the explicit
`sdd-code-design` call and return contract in [diagnosis](diagnosis.md). Limit the
questions to the affected contracts, mechanisms and consumers.

Before comparing values, compare tool versions, configurations, source sets,
variants, exclusions, history windows, mapping, graph node normalization and row
populations. Changed definitions require recalculating both revisions or separate
series. Never subtract incomparable values to claim improvement. The scripts do
not automate a semantic comparison between configurations.

After implementation of a selected recommendation, link the original card,
diagnosis, snapshot and acceptance to the observed implementation. An earlier
report is a hypothesis to verify, not evidence of current completion. Reconcile
changed sources and decisions through [basis reassessment](continuation.md#reconcile-a-changed-basis),
then assign these checks within the relevant scope:

1. Check the acceptance scenario: what change became more local, what consumer
   knowledge was removed, which contract misuse became impossible, or which
   unwanted dependency disappeared? Contract protection can improve while graph
   and complexity measurements stay unchanged.
2. Run relevant existing behavior checks, including tests delivered with the
   implementation, compilation of affected code and consumers, and an existing
   wiring integration scenario when wiring materially changed. Select tasks from
   the actual Gradle build. Record missing acceptance protection as a gap and a
   bounded follow-up proposal; this audit does not add tests or build tasks.
3. Check package conventions and the applicable ArchUnit rule, including imported
   consumer classes. Reuse a suitable rule; propose one only for an uncovered
   accepted boundary. Count neither rules nor green tests as a modularity metric.
4. Recalculate only the related measurements under comparable definitions. After
   moving or splitting files compare the entire original responsibility, its new
   parts and changed consumers. File splitting can game CRAP_file; sums of MCC can
   also grow when newly extracted functions each acquire their base unit. Related
   graph measurements can require the full affected graph rather than a file-only
   sample; document the population used.
5. Distinguish immediate structural/behavioral evidence from later observed change
   locality. Use subsequent real history when a relevant change happens. No such
   change yet means the long-term benefit is untested.

If an outcome differs from the prediction, identify whether the data, diagnosis,
chosen transformation or implementation was wrong. Revise affected recommendations.
More coverage does not demonstrate modularity; lower PC does not measure speed.
Reopen the audit after a meaningful contract change, new problem or the project's
chosen review cycle, proportionate to the cost of collection.

Finish through a fresh integration architect and the final-report contract. State
which expected effects are supported, contradicted or still untested, with exact
source/check evidence and consequences for dependent cards. Preserve unknown
coverage and source identity as limitations; missing execution is not a pass.
Validate changed cards against their current snapshot with assigned `rank` checks.
Save the authored `report.md` in the report directory and return its link, including
when the result is only unresolved findings. Implementing a recommendation or
repairing the reviewed change requires a separate instruction.
