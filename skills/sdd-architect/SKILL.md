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

## Default route: full cycle

A bare `$sdd-architect`, `/sdd-architect`, or skill selection without additional
task text starts the full working sequence: **collect metrics → analyze metrics
and source code → deliver concrete recommendations**. General audit and refactoring
requests use the same route. Start from the current project's checkout and discover
its scope and build configuration; an omitted prompt is not a request to choose a mode.

Read Collection first, then load the later references as their stages begin.
Carry the task through the final recommendation report, linking the snapshot,
analysis and cards. Record unavailable measurements as gaps and qualify the
recommendations accordingly. Existing reports are inputs to qualify within this
cycle; their presence does not select a reports-only route.

Use a focused route only when the user explicitly asks for one, such as analyzing
supplied reports, comparing given proposals, reviewing a diff or reassessing a
completed change. Ask for a project location only when the working context does
not identify a suitable Kotlin/Gradle checkout.

## Read by stage or explicit focus

| Situation | Read at this point | Result |
| --- | --- | --- |
| Start the full cycle or fill measurement gaps | [Collection](references/collection.md), then [runtime](references/runtime.md) before any script | Reproducible snapshot and explicit collection gaps; continue to analysis and recommendations |
| Explicit request to analyze existing reports, including reports without sources | [Collection](references/collection.md), import branch | Qualified snapshot; source-free results remain hypotheses |
| Calculate or interpret a signal | [Measurements](references/measurements.md) | Deterministic views and an investigation shortlist |
| Diagnose candidates and compare changes | [Diagnosis](references/diagnosis.md), including its explicit `sdd-code-design` call | Source-grounded findings and a feasible change per recommendation |
| Prioritize and deliver | [Decision output](references/decision-output.md) | Validated cards, tied priority groups and execution dependencies |
| Review a diff or verify an implemented recommendation | [Reassessment](references/reassessment.md) | Comparable evidence for the affected code and consumers |

Read only the references required by the current stage. Execute
[metrics.py](scripts/metrics.py) for `identity`, `collect`, `analyze`, and `rank`;
use its `--help` for arguments. Keep formulas in the supplied scripts. Scripts
calculate observations; the agent establishes responsibilities, mechanisms and effects.

## Full working sequence

1. Fix the revision, working changes, source sets, package ownership and scope.
   Use existing architecture decisions and tests; label inferred boundaries as hypotheses.
2. Collect or qualify the necessary inputs. Unknown coverage is not 0%; an unknown
   revision prevents implementation-ready recommendations. A local data defect limits
   the affected claim rather than invalidating unrelated source evidence.
3. Calculate views and shortlist 8–12 candidate groups. Merge signals for the same
   area before selecting; retain important candidates justified by a known risk
   or upcoming change even without a hotspot signal.
4. Explicitly read the sibling [sdd-code-design skill](../sdd-code-design/SKILL.md)
   and its [focused diagnosis](../sdd-code-design/workflows/diagnose-code.md) workflow.
   Apply it to each source-available candidate group using the
   [request and return contract](references/diagnosis.md). Inspect findings and
   compare the current system with a concrete change. Source-free candidates
   remain questions for investigation.
5. Separate ready recommendations, decision-changing checks, observations and rejections.
   Validate and order the authored cards with `rank`. Explain each strict priority
   difference through the scenario, keeping ties visible.

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
