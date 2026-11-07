# Diff review and post-change reassessment

For a diff, fix base and target revisions and inspect the affected consumers even
when they are outside the diff. Collect separate snapshots through the same
configuration. Read a particular graph at its own level; a package cycle is not a
class cycle. Use the same package map unless the change explicitly revises it.

For source-available diff candidates or a reopened diagnosis, use the explicit
`sdd-code-design` call and return contract in [diagnosis](diagnosis.md). Limit the
questions to the affected contracts, mechanisms and consumers.

Before comparing values, compare tool versions, configurations, source sets,
variants, exclusions, history windows, mapping, graph node normalization and row
populations. Changed definitions require recalculating both revisions or separate
series. Never subtract incomparable values to claim improvement. The scripts do
not automate a semantic comparison between configurations.

After implementation of a selected recommendation:

1. Check the acceptance scenario: what change became more local, what consumer
   knowledge was removed, which contract misuse became impossible, or which
   unwanted dependency disappeared? Contract protection can improve while graph
   and complexity measurements stay unchanged.
2. Run relevant existing/new behavior checks, compilation of affected code and
   consumers, and a wiring integration scenario when wiring materially changed.
   Select tasks from the actual Gradle build. Do not require new tests for already
   covered behavior solely to fill a template.
3. Check package conventions and the applicable ArchUnit rule, including imported
   consumer classes. Reuse a suitable rule; add one only for an uncovered accepted
   boundary. Count neither rules nor green tests as a modularity metric.
4. Recalculate only the related measurements under comparable definitions. After
   moving or splitting files compare the entire original responsibility, its new
   parts and changed consumers. File splitting can game CRAP_file; sums of MCC can
   also grow when newly extracted functions each acquire their base unit.
5. Distinguish immediate structural/behavioral evidence from later observed change
   locality. Use subsequent real history when a relevant change happens. No such
   change yet means the long-term benefit is untested.

If an outcome differs from the prediction, identify whether the data, diagnosis,
chosen transformation or implementation was wrong. Revise affected recommendations.
More coverage does not demonstrate modularity; lower PC does not measure speed.
Reopen the audit after a meaningful contract change, new problem or the project's
chosen review cycle, proportionate to the cost of collection.
