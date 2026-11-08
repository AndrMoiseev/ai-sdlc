---
name: sdd-architect
description: Full-cycle metrics collection, analysis and source-grounded refactoring recommendations for Kotlin/JVM and Gradle projects, by explicit invocation.
disable-model-invocation: true
---

# SDD Architect

Run only after an explicit `$sdd-architect`, `/sdd-architect`, or user selection
of this skill. Follow-up messages continue the selected workflow without another invocation.

Deliver up to five concrete, source-grounded recommendations, a short investigation
queue, and the important rejected candidates. Prioritize **modularity → regression
risk reduction → development speed**. Preserve uncertainty instead of manufacturing
a quality score.

An architectural module is a declared group of packages with a responsibility,
public contract and dependency rules. Gradle projects describe collection scope.
Recommend package conventions and ArchUnit checks for boundaries; creating or
splitting Gradle projects is outside this method.

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
task text starts all four phases: **configuration → evidence → analysis → final
report**. General audit and refactoring
requests use the same route. Start from the current project's checkout and discover
its scope and build configuration; an omitted prompt is not a request to choose a mode.

Read the [four-phase workflow](references/workflow.md) before starting. Before
dispatch, continuation or handoff, read
[assignments and context](references/orchestration.md) for saved requests/results,
current input basis, fresh contexts and single-writer ownership.
The orchestrator runs the phases sequentially through `report.md`, without
intermediate user approvals for the already requested audit. Existing reports are
inputs to qualify within this cycle; their presence does not select a reports-only route.

| Phase | Assigned work | Completion artifact |
| --- | --- | --- |
| 1. Configuration | Explorer researches scope and proposes configuration; orchestrator saves it before identity capture | Project configuration and `collection-plan.md` |
| 2. Evidence | Fresh explorer executes exact assigned checks and reports measurement results or gaps | Raw reports, immutable snapshot and deterministic analysis views |
| 3. Analysis | Architect makes an 8–12 group shortlist; a fresh architect diagnoses each related group | Shortlist and source-grounded diagnoses with alternatives and uncertainty |
| 4. Final report | Fresh architect integrates diagnoses and authors cards; orchestrator assigns `rank` to explorer | Validated ordering and `report.md`, with up to five ready recommendations |

Use an [explicit focused route](references/continuation.md#explicit-focused-routes)
only when the user asks for one, such as analyzing supplied reports, comparing
given proposals, reviewing a diff or reassessing a completed change. Ask for a
project location only when the working context does not identify a suitable
Kotlin/Gradle checkout.

## Read by stage or explicit focus

| Situation | Read at this point | Result |
| --- | --- | --- |
| Research configuration or collect missing measurements | [Collection](references/collection.md), then [runtime](references/runtime.md) before any script | Justified scope, reproducible snapshot and explicit collection gaps |
| Explicit request to analyze existing reports, including reports without sources | [Focused routes](references/continuation.md#explicit-focused-routes), then [collection import](references/collection.md#import-existing-reports) | Qualified snapshot; source-free results remain hypotheses |
| Calculate or interpret a signal | [Measurements](references/measurements.md) | Deterministic views and an investigation shortlist |
| Diagnose candidates and compare changes | [Diagnosis](references/diagnosis.md), including its explicit `sdd-code-design` call | Source-grounded findings and a feasible change per recommendation |
| Prioritize and deliver | [Decision output](references/decision-output.md) | Validated cards, tied priority groups and execution dependencies |
| Review a diff or verify an implemented recommendation | [Reassessment](references/reassessment.md) | Comparable evidence for the affected code and consumers |
| Request more evidence, resume after interruption or reconcile a changed basis | [Continuation](references/continuation.md) | Bounded follow-up, verified saved work and the next affected phase |

Read only the references required by the current phase. The orchestrator uses
the shared `sdd-spec.architect` and `sdd-spec.explorer`
[selection keys](../sdd-shared/references/subagents.md) and their role instructions;
this audit does not invoke the `sdd-spec` planning workflow. Role instructions
define work quality; this workflow defines assignments, documents and transitions.

Assign [metrics.py](scripts/metrics.py) commands `identity`, `collect`, `analyze`
and `rank` to explorer through the shared checks contract. Keep formulas in the
supplied scripts. Scripts calculate observations; architects establish
responsibilities, mechanisms and effects. The orchestrator launches all roles
and handles requests for further research or checks.

Before declaring a recommendation ready, verify its source evidence, feasible
transformation, required behavior, acceptance check and three effect judgments.
Readiness never follows from crossing a metric threshold. Preparation tests belong
to their parent change; they do not earn its benefit a second time.

## Boundaries and common mistakes

- End this task with recommendations. Implement source changes only under a separate instruction.
- Preserve required product behavior. Add compatibility work only when explicitly required.
- Treat SCC, PC and visibility as related observations of one graph; treat MCC,
  coverage and file CRAP as related inputs. Their weights are not additive.
- Keep zero, unknown and not-applicable distinct. Keep source locations and declarations;
  resolve overload signatures from code before publishing a card.
- Request more evidence only when a feasible check can change the decision.
  A stable shared contract, high external affinity or a high Martin distance can be acceptable.

The method and its limits are traced in [provenance](references/provenance.md).
