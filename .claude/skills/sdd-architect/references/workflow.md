# Four-phase architecture audit

The orchestrator owns assignments and phase transitions. Start with
[report storage and runtime](runtime.md), then follow the phases below in order.
A bare invocation authorizes the complete audit through `report.md`; phase
completion is an evidence check, not an additional user approval.

Before dispatch, continuation or handoff, use
[assignments and context](orchestration.md): saved requests and results, exact input
basis, shared role selection, fresh contexts and verified writer transfer. Execute
assignments sequentially. The orchestrator receives requests for additional research
or checks; architects author assigned analysis and explorers produce assigned
evidence. Product sources remain read-only throughout the audit.

For a bounded evidence request, changed basis or interrupted audit, use
[continuation](continuation.md). Save the current phase and primary record links
in `state.md`; resume from verified artifacts and host state.

## Phase 1: Configuration

**Input:** project checkout, requested audit scope and constraints, existing
collection configuration, architecture decisions and build/source evidence.

1. Start a fresh explorer with a research question covering production source roots, Gradle
   projects and variants, compiled outputs, existing measurement/test tasks,
   exclusions and package ownership. Apply [Collection](collection.md).
   Inspect existing reports for possible reuse and retain their original provenance.
2. Require a proposed configuration and collection plan with source references
   explaining the scope choices. Inventory all five measurement families:
   dependencies, history, source size, complexity and coverage. For each family,
   name its intended input or exact collection command, output and known limitation.
   Label inferred module boundaries and unknown ownership explicitly.
3. Reconcile the proposal against the user's scope and current project evidence.
   The orchestrator writes `.sdd/architect/collection.json` and
   `<report-dir>/collection-plan.md` before capturing identity. Explorer requests
   configuration changes in its result; it does not edit project configuration
   or `.sdd/settings.json`.

Register commands in the collection plan under the
[checks contract](orchestration.md#register-checks-in-the-collection-plan).
Research proposes commands; builds, tests and measurements require an assigned
checks set. Use existing tasks and record an unavailable task as a gap rather
than changing the product build during the audit.

**Exit:** the saved configuration and plan agree on source/build scope, exclusions,
ownership and all five families. Every scope choice has evidence or an explicit
assumption. An omitted source set is a stated limit, not an invisible default.

## Phase 2: Evidence

**Input:** saved configuration and collection plan, exact registered commands,
current source basis and permitted evidence destinations.

1. Start a fresh explorer with a `checks` assignment. The orchestrator supplies
   exact `check_ids`, stage and registry revision under the shared contract.
   Execute identity capture, existing build/report tasks, `collect` and `analyze`
   in their recorded dependency order. Keep configuration stable during each
   `identity` or `collect` command.
2. Return verified provenance from compilation and report generation to the
   orchestrator. It saves those configuration values before the dependent
   collection batch. A dependent batch receives an updated assignment and basis;
   explorer never edits configuration to make a check pass.
3. Retain raw reports and logs, captured identity, immutable snapshot and
   deterministic analysis views in the report directory. Each measurement family
   returns its result and provenance or a concrete gap: failed command, absent
   tool/input, unsuitable population, unknown identity or unavailable permission.
   Preserve partial usable evidence and the distinction between zero and unknown.
4. Return a compact result with assignment identity, command outcomes, source
   basis, family coverage/gaps and artifact references. Full report bodies remain
   in files. Use the collector's compact stdout; the orchestrator reads summaries
   and forwards evidence references rather than loading raw dumps into its context.

**Exit:** retained snapshot and analysis views cover the declared scope; all five
families have a result or precise gap. The orchestrator checks actual artifacts
and source identities against the assignment. Successful execution alone does not
prove complete measurements. A missing family limits its dependent claims;
unavailable execution capability stops only the dependent work. Unknown revision
or source identity prevents implementation-ready recommendations.

## Phase 3: Analysis

**Input:** qualified snapshot, deterministic views, scope/gaps, source references
and the known change or behavior scenario.

1. Start a fresh architect for the shortlist. Use [Measurements](measurements.md) to select
   8–12 related candidate groups, merging signals for the same area. Include a
   known risk, critical contract or upcoming change even without a hotspot signal.
   If the source population supports fewer distinct groups, explain that bound.
   Retain selection reasons and material omissions in `diagnosis.md`.
2. Record for each group its identity, paths/declarations, qualified signals,
   scenario and the owner, consumers, wiring and tests needed to investigate it.
   A group may cross package or module boundaries; the cause can belong to a cold
   dependency. The group is an investigation scope, not a module definition.
3. Start a fresh architect for each group's bounded diagnosis. Pass the saved
   group and evidence references, required behavior, known limits and one assigned
   `diagnoses/<group-id>/diagnosis-<n>.md` output. Require the explicit `sdd-code-design` focused diagnosis
   call in [Diagnosis](diagnosis.md). Each architect inspects that group's mechanism
   and affected consumers; it does not repeat a repository-wide audit.
4. Require source evidence, alternative explanations and transformations,
   preservation of required behavior, cost/risk, acceptance and separate confidence
   in observation, diagnosis and expected effect. Each result proposes `ready`,
   `needs_check`, `observe` or `rejected` with the grounds required by
   [stop conditions](diagnosis.md#stop-conditions). Source-free groups return
   questions and limits. A proposed check is distinct from an executed check.

After the shortlist author's verified stop, the orchestrator links each separate
diagnosis from the shortlist under the [context and writer contract](orchestration.md#choose-the-context-boundary).
Keep expansions to owners/consumers explicit and bounded by the causal question.
Route [bounded evidence requests](continuation.md#request-bounded-evidence) through
the orchestrator; existing raw evidence can be opened without rerunning its command.

**Exit:** every shortlisted group has a returned diagnosis or a specific unresolved
gap with its decision consequence. The retained result includes justified non-issues;
neither a finding count nor a metric threshold establishes readiness.

## Phase 4: Final report

**Input:** shortlist, bounded diagnoses and their evidence references, snapshot,
analysis views, current scope/gaps and source basis.

1. Start a fresh architect for integration. Merge diagnoses that share a cause,
   retain important non-issues and resolve contradictory claims against their
   source evidence. Request bounded follow-up research/checks through the
   orchestrator when an attainable answer changes the decision. Preserve an
   unresolved contradiction as uncertainty in the affected recommendation.
2. Check dependencies across the complete set: changed owners and contracts,
   affected consumers, conflicting transformations, prerequisites and required
   behavior. Compare the current system with the smallest useful change and a
   broader option when meaningful. Avoid awarding one cause or preparation test
   the same benefit twice.
3. Apply [Decision output](decision-output.md) to author `cards.json`. Establish
   readiness and each M/R/S effect from mechanisms, feasible transformations and
   acceptance. Write the substantive reason for each strict priority difference;
   equal effects remain tied. An unresolved trade-off keeps its effect unknown.
4. The architect returns completed cards and stops dependent writing. The orchestrator
   assigns `rank` to explorer as exact registered checks against that retained cards
   version and its snapshot. Save the full result and optional generated
   Markdown separately from `report.md`. Return validation failures to the
   architect for correction against the evidence, then assign checks on the
   changed input. `rank` validates and orders authored claims; it cannot prove
   that a diagnosis is true.
5. Continue the integrating architect with the saved ranking result and current
   input basis under [the handoff contract](orchestration.md#accept-the-handoff). Finish `report.md`
   with source evidence, actual scope and gaps, up to five ready recommendations,
   their grounded priority rationale and dependencies, the investigation queue,
   observations and important rejections. Link the snapshot, analysis, diagnoses,
   cards and ranking. Zero ready recommendations is a valid completed result.

**Exit:** report conclusions agree with retained evidence and validated ordering;
unresolved items remain visibly unresolved. The orchestrator returns the report
link and a brief account of the recommendations and material limitations.
