# Diff review and post-change reassessment

Use these [explicit focused routes](continuation.md#explicit-focused-routes)
within the workflow contracts. The orchestrator maintains configuration on a
run with a checkout, registers exact comparison/acceptance checks, and records
the phase, basis and unresolved work in `state.md`. Explorers collect evidence;
architects diagnose and integrate it. Keep source changes outside this audit.

Use a supplied diff or the requested Git comparison to locate affected code.
Read the current implementation and consumers, including those outside the diff.
A comparison's historical references describe that input only; do not capture or
verify the audited source version. Collect relevant current measurements when
they can answer the question, retaining separate report directories and their
measurement definitions. A package cycle is not a class cycle. Explain any change
to declared ownership instead of inferring it from moved files.

For source-available diff candidates or a reopened diagnosis, use the explicit
`sdd-code-design` call and return contract in [diagnosis](diagnosis.md). Limit the
questions to the affected contracts, mechanisms and consumers.

Before comparing values, compare tool versions, configurations, source sets,
variants, exclusions, history windows, mapping, graph node normalization and row
populations. Obtain each collection's [analysis policy](analysis-policy.md) through
the script and compare its measurement parameters and selection thresholds.
Use separate series when definitions differ; calculate current
values under the needed definition if that resolves the question. Never subtract incomparable values to claim improvement. The scripts do
not automate a semantic comparison between configurations.

After implementation of a selected recommendation, link the original card,
diagnosis, keyed measurements and the effect criteria in section 6 to the observed
implementation. Obtain detailed acceptance checks from the resulting `sdd-spec`
design and plan when available. An earlier
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
chosen transformation or implementation was wrong. Record revised recommendations
in the new audit and link their predecessors; retain the original audit cards.
More coverage does not demonstrate modularity; lower PC does not measure change
cost reduction. Compare representative accepted changes before and after when
token, human-effort or elapsed-time telemetry exists; preserve comparable model,
execution setup and acceptance conditions. Otherwise retain a qualitative effect
claim and its limits.
Reopen the audit after a meaningful contract change, new problem or the project's
chosen review cycle, proportionate to the cost of collection.

Finish through a fresh integration architect and the final-report contract. State
which expected effects are supported, contradicted or still untested, with exact
source/check evidence and consequences for dependent cards. Preserve unknown
coverage and measurement completeness as limitations; missing execution is not a pass.
Validate changed cards using current sources and keyed JSONL evidence with assigned `rank` checks.
Save the authored `report.md` in its timestamped audit directory and complete
[plan maintenance](tech-debt-plan.md), including when the result is only unresolved
findings. Existing task reassessments are reported for the user's decision; automatic
admission adds only new eligible tasks. Return report and plan links and excluded-status
notifications. Implementing a recommendation or
repairing the reviewed change requires a separate instruction.
