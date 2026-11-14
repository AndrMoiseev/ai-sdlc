---
name: sdd-architect
description: Full-cycle metrics collection, analysis and source-grounded refactoring recommendations for Kotlin/JVM and Gradle projects, by explicit invocation.
disable-model-invocation: true
---

# SDD Architect

Run only after an explicit `$sdd-architect`, `/sdd-architect`, or user selection
of this skill. Follow-up messages continue the selected workflow without another invocation.

Deliver up to five source-grounded refactoring directions for human-involved
development through `sdd-spec`, a short investigation
queue, and the important rejected candidates. Prioritize **modularity → regression
risk reduction → development speed**. Preserve uncertainty instead of manufacturing
a quality score.

An architectural module is a declared group of packages with a responsibility,
public contract and dependency rules. Gradle projects describe collection scope.
Describe proposed boundaries through responsibilities and dependency directions.
Detailed package contracts and ArchUnit checks belong to subsequent `sdd-spec`
work; creating or splitting Gradle projects is outside this method.

## Project configuration and report directory

For every run with a project checkout, the orchestrator saves the researched
configuration in `.sdd/architect/collection.json` through
[project configuration maintenance](references/collection.md#maintain-project-configuration).
Explorer proposes the configuration; the orchestrator owns its persistence.

Before producing any materials, establish
`<project-root>/docs/reports/{report-name}/` using the
[report storage contract](references/runtime.md#report-storage). Save the final
report and all intermediate materials there for every route, including focused
analysis and reassessment. Finish with a link to its `report.md`.

## Default route: full cycle

A bare `$sdd-architect`, `/sdd-architect`, or skill selection without additional
task text starts **configuration → collect → analysis → ranking → final
report**. General audit and refactoring
requests use the same route. Start from the current project's checkout and discover
its scope and build configuration; an omitted prompt is not a request to choose a mode.

Read the [workflow](references/workflow.md) before starting. Before
dispatch, continuation or handoff, read
[assignments and context](references/orchestration.md) for saved requests/results,
current input basis, fresh contexts and single-writer ownership.
The orchestrator runs the phases sequentially through `report.md`, without
intermediate user approvals for the already requested audit. Existing reports are
inputs to qualify within this cycle; their presence does not select a reports-only route.

| Phase | Assigned work | Completion artifact |
| --- | --- | --- |
| 1. Configuration | Explorer researches scope and proposes configuration; orchestrator saves it | Project configuration and `collection-plan.md` |
| 2. Collect | Fresh explorer executes assigned checks; `collect` calculates measurements, preliminary groups and investigation order | Raw inputs, JSONL measurements/selections, groups with overlaps and a budgeted queue; compact `collection.json` |
| 3. Analysis | Architect refines the computed shortlist; fresh architects diagnose groups and integrate recommendations | Six-section Markdown cards with evidence and open design questions; compact ranking metadata |
| 4. Ranking | Explorer executes assigned `rank` against the cards, collection and current sources | Checked card structure, evidence addresses and priority groups |
| 5. Final report | Fresh architect authors the report from diagnoses, cards and ranking | `report.md`, with up to five ready recommendations |

Use an [explicit focused route](references/continuation.md#explicit-focused-routes)
only when the user asks for one, such as analyzing supplied reports, comparing
given proposals, reviewing a diff or reassessing a completed change. Ask for a
project location only when the working context does not identify a suitable
Kotlin/Gradle checkout.

## Read by stage or explicit focus

| Situation | Read at this point | Result |
| --- | --- | --- |
| Research configuration or collect missing measurements | [Collection](references/collection.md), then [runtime](references/runtime.md) before any script | Justified scope, complete measurement catalog and explicit gaps |
| Explicit request to analyze existing reports, including reports without sources | [Focused routes](references/continuation.md#explicit-focused-routes), then [collection import](references/collection.md#import-existing-reports) | Qualified JSONL evidence; source-free results remain hypotheses |
| Calculate or interpret a signal | [Measurements](references/measurements.md) | Deterministic views and keyed signals |
| Prepare or refine the investigation shortlist | [Candidate groups](references/candidate-groups.md) | Computed groups and ordering; source-grounded shortlist adjustments |
| Diagnose candidates and compare directions | [Diagnosis](references/diagnosis.md), including its explicit `sdd-code-design` call | Source-grounded findings and a justified refactoring direction |
| Author cards, prioritize and deliver | [Decision output](references/decision-output.md) | Six-section Markdown cards, tied priority groups and evidence for `sdd-spec` |
| Review a diff or verify an implemented recommendation | [Reassessment](references/reassessment.md) | Comparable evidence for the affected code and consumers |
| Request more evidence, resume after interruption or reconcile a changed basis | [Continuation](references/continuation.md) | Bounded follow-up, verified saved work and the next affected phase |

Read only the references required by the current phase. The orchestrator uses
the shared `sdd-spec.architect` and `sdd-spec.explorer`
[selection keys](../sdd-shared/references/subagents.md) and their role instructions;
this audit does not invoke the `sdd-spec` planning workflow. Role instructions
define work quality; this workflow defines assignments, documents and transitions.

Assign [metrics.py](scripts/metrics.py) commands `collect` and `rank` to explorer
through the shared checks contract. Keep formulas in the
supplied scripts. Scripts calculate observations; architects establish
responsibilities, mechanisms and effects. The orchestrator launches all roles
and handles requests for further research or checks.

Use current source paths, task scope and keyed JSONL evidence throughout the audit,
including continuation and reassessment. The audit has no source-version binding:
do not capture or compare commit IDs, working-tree cleanliness, source fingerprints
or artifact checksums. A later commit containing the report supplies only its
ordinary repository history. Historical commit IDs may address change events.

Before declaring a recommendation ready, apply the six-section card and readiness
contract in [decision output](references/decision-output.md). Readiness means enough
evidence to discuss the direction with a human in `sdd-spec`. It does not require
a finished design or implementation plan and never follows from a metric threshold.

## Boundaries and common mistakes

- End this task with directions and evidence. Start detailed design or implementation only under a separate instruction.
- Preserve required product behavior. Add compatibility work only when explicitly required.
- Treat SCC, PC and visibility as related observations of one graph; treat MCC,
  coverage and file CRAP as related inputs. Their weights are not additive.
- Keep zero, unknown and not-applicable distinct. Keep source locations and declarations;
  resolve overload signatures from code before publishing a card.
- Request more evidence only when a feasible check can change the decision.
  A stable shared contract, high external affinity or a high Martin distance can be acceptable.

The method and its limits are traced in [provenance](references/provenance.md).
