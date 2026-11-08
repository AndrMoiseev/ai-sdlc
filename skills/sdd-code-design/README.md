# sdd-code-design

This skill is a fork of [CodeAlive-AI's original skill](https://github.com/CodeAlive-AI/ai-driven-development/tree/main/skills/code-that-fits-in-your-head), imported from commit [`79d911b`](https://github.com/CodeAlive-AI/ai-driven-development/commit/79d911b773d83986bee7ac4170d09a972e61fe31). Changes from upstream are listed below.

Cross-agent skill for keeping software understandable and inexpensive to change. It helps prevent accidental complexity, architectural erosion into a Big Ball of Mud, and silent technical-debt accumulation—especially when coding agents can generate code faster than people can review and own it.

The skill is based on Mark Seemann's *Code That Fits in Your Head: Heuristics for Software Engineering* (2021), with clearly labelled editorial amendments for agent-driven development.

Invoke it explicitly with `$sdd-code-design` in Codex or `/sdd-code-design` in Claude Code. A sibling APM skill can also explicitly instruct the agent to read `../sdd-code-design/SKILL.md`, relative to its own directory, and apply it to a named task. Implicit invocation remains disabled; task relevance or a passing mention alone does not activate it.

Use it when a task is about:

- designing complex code, APIs, domain types, validation boundaries, and invariants
- decomposing tangled functions, classes, workflows, or subsystems
- reviewing code for readability, cohesion, coupling, encapsulation, and testability
- diagnosing a selected hotspot, contract, or change scenario before choosing a refactoring
- adding features outside-in with tests and a walking skeleton
- debugging defects with reproducible tests, bisection, and tighter verification loops
- evolving legacy systems with feature flags, Strangler-style migration, reversible stages, and explicit verification
- threat-modelling endpoints or services with STRIDE
- reviewing agent-generated changes for architectural fit, verification integrity, dependency provenance, and new debt

Large tasks are not rejected because they are large. Agents can successfully implement changes spanning tens of thousands of lines when the work has coherent architecture, a clear plan, trustworthy acceptance criteria, and verifiable checkpoints. The skill targets unstructured complexity and unverifiable change—not scope by itself.

## How It Works

`SKILL.md` contains the explicit invocation policy and top-level index. `guidelines.md` is the routing layer: it maps tasks, symptoms, and named practices to the smallest useful reference files.

Code examples include the original C# material and Kotlin/JVM and Go counterparts; every rule and the tooling tables are language-neutral. Use [Examples by Stack](guidelines.md#examples-by-stack) to select the matching language and dependencies.

The skill uses progressive disclosure. Load one primary file and at most one or two secondary files for the current task instead of reading the whole skill. Focused diagnosis returns findings. Tasks that authorize lasting gates or project-instruction edits can operationalize a repeatedly useful rule (`workflows/operationalize-finding.md`).

### Focused code diagnosis

[sdd-architect](../sdd-architect/README.md) uses this route after selecting candidates
from metrics or a known risk/change scenario. The diagnosis follows the relevant
contracts, consumers and tests, including a rarely changed dependency that may
own the cause. It returns evidence, applicable heuristics, mechanisms, feasible
options and acceptance checks. The architect decides recommendation readiness and
priority across candidates. A diagnosis can also conclude that no change is justified.

For interface changes, the diagnosis compares what consumers must know or do before
and after, including obligations beyond method signatures. For suspected redundant
abstractions, it traces what their removal would eliminate, move to consumers or
leave without an owner. This helps distinguish unnecessary forwarding from a useful
thin boundary.

When domain operations expose storage or transport details, the diagnosis compares
a plausible business-rule change with a representation change and shows which
consumers and tests each affects. When a proposed extraction moves effects, it
checks required read order, failure handling and resource ownership. A read-only
query is not assumed to be a pure calculation.

| Request | Example prompt | Result |
| --- | --- | --- |
| Diagnose a hotspot | `$sdd-code-design Diagnose the frequently changed OrderService and its contracts. Check the risk of mixing customer and order IDs. Return findings without editing code.` | A scoped diagnosis with source evidence, existing protection, options and checks |
| Diagnose an upcoming change | `$sdd-code-design Diagnose the pricing contract before we add regional rounding rules. Inspect its consumers even though the contract rarely changes.` | An explanation of change risks and feasible improvements, with uncertainty stated |
| Compare an interface proposal | `$sdd-code-design Diagnose whether the proposed pricing facade simplifies its consumers. Compare the current contract with the proposal without editing code.` | A concrete comparison of consumer obligations, their owners and acceptance checks |
| Assess a thin abstraction | `$sdd-code-design Diagnose the forwarding chain in the pricing module. Determine whether removing a layer is justified; return findings without editing code.` | An explanation of overhead removed, knowledge redistributed and responsibilities that must survive |
| Compare semantic boundaries | `$sdd-code-design Diagnose the booking policy, which reads storage fields directly. Compare changing the party-size rule with changing the timestamp representation. Return findings without editing code.` | A comparison of affected owners, consumers and tests, with the smallest useful boundary change |
| Check a proposed pure pipeline | `$sdd-code-design Review the proposed extraction of the publication loop into a pure calculation. The input is streamed and publication failure must stop further reads. Check clock and storage reads, error handling and resource lifetime.` | A diagnosis of purity and effect-ordering risks, with acceptance checks for the required behavior |

Diagnosis does not require a PR or a high metric value. Its result covers the
inspected area; it does not certify the whole codebase or start implementation.

## Structure

```text
SKILL.md                 # Invocation policy, philosophy, chapter index
guidelines.md            # Task/symptom/practice routing
workflows/               # Step-by-step workflows for common engineering tasks
references/              # Focused reference packs by theme
references/tooling/      # Executable measurement commands (complexity, cycles, dead code, …)
```

Core themes include decomposition, encapsulation, API design, outside-in TDD, separation of concerns, teamwork and Git discipline, software evolution, troubleshooting, security, and measurement tooling. Workflows cover focused diagnosis, review, outside-in features, debugging, threat modelling, and operationalizing findings into gates.

## Source Boundaries

Most reference folders summarize or operationalize ideas from Seemann's book. The `references/agent-native/` folder is different: it contains local editorial additions for coding agents—verification integrity, hallucination and dependency grounding, executable guardrails, and accountable review. Editorial amendments placed in book-derived themes are explicitly marked. Do not attribute them to Seemann.

### Stratified design sources

The semantic-layer reference and the additions about moving effects draw on
[j2h4u/skill-stratified-design at commit 6f0957e](https://github.com/j2h4u/skill-stratified-design/tree/6f0957e60521b886c3bcbcea2f8260ebfe8cc8f5).
They are additions to this skill, not material from Seemann's book. Their
attributions and source history belong here; the agent instructions contain the
applicable rules and examples.

- [SICP, section 2.2.4](https://sicp.sourceacademy.org/chapters/2.2.4.html)
  supplies the model of successive languages with primitives, combinations and
  abstractions.
- Eric Normand develops the practical approach in *Grokking Simplicity*, chapters
  8–9, and [More about Stratified Design](https://ericnormand.me/podcast/more-about-stratified-design).
  [What is an action?](https://ericnormand.me/podcast/what-is-an-action) and
  [What is a calculation?](https://ericnormand.me/podcast/what-is-a-calculation)
  explain time-dependent actions and calculations from explicit inputs.
- The paired business-rule and representation-change comparison is the external
  skill author's [application of those ideas](https://github.com/j2h4u/skill-stratified-design/blob/6f0957e60521b886c3bcbcea2f8260ebfe8cc8f5/references/author-notes.md#L49-L61).
  Its [worked example](https://github.com/j2h4u/skill-stratified-design/blob/6f0957e60521b886c3bcbcea2f8260ebfe8cc8f5/references/worked-example.md)
  illustrates why publication failure must stop further input consumption.
- The CQS Query versus pure-calculation distinction, conditional routing and
  integration into the existing diagnosis are local adaptations. The booking
  example and agent instructions are written for this skill.

The external skill's original guidance is [MIT-licensed](https://github.com/j2h4u/skill-stratified-design/blob/6f0957e60521b886c3bcbcea2f8260ebfe8cc8f5/LICENSE),
copyright 2026 j2h4u. Its separately licensed SICP excerpt uses CC BY-SA 4.0;
that excerpt is not included here. These additions paraphrase the ideas and do
not copy the external implementation or introduce a runtime dependency.

## Governing Principles

- Prefer simple, cohesive designs over clever or speculative abstractions.
- Keep dependencies, side effects, and ownership boundaries explicit.
- Judge complexity across the system, not only inside individual methods.
- Require verification proportional to risk and independent of the implementation where it matters.
- Never weaken tests, types, CI, or security controls merely to make generated code pass.
- Treat generated code volume, merge rate, and approval speed as poor proxies for maintainability.

## Adding a Language or Stack

1. **Use the C# document as the structural template where applicable.** When every source example has a meaningful, idiomatic counterpart, preserve the heading hierarchy, example numbering and order, bad/good examples, before/after comparisons, and refactoring steps. When a counterpart does not fit the target language or stack, explain the omission or adaptation briefly. Retain the original order and identifiers of supported examples so readers can compare them.
2. **Separate examples by their actual dependencies.** Place examples in `references/<topic>/examples/<language>[-<technology>].md`. Use lowercase names with hyphens, such as `python.md`, `python-pytest.md`, or `kotlin-ktor-junit5.md`. Keep framework-independent examples in the language file and framework-specific examples in qualified files. State each file's scope and which source examples it covers.
3. **Preserve existing material.** Keep existing examples and shared rules unchanged when adding a stack. If a topic still has an `examples.md`, move it intact into `examples/` under its stack name and update its references. Label new examples as fork additions and retain upstream attribution.
4. **Express the principle idiomatically within the matching section.** Use the target language's conventions for errors, nullability, invariants, composition, and testing. Retain the original scenario and teaching purpose; explain necessary language-specific differences alongside the corresponding example. Distinguish compile-time guarantees from runtime checks; state simplifying domain assumptions and limits.
5. **Make examples reproducible.** Include imports, required definitions, dependencies, and compatible versions. Explain which blocks form one program and which are independent alternatives or migration stages. Keep setup notes brief and place supporting code with the relevant example, preserving the original document outline. Clearly label intentionally incorrect examples.
6. **Verify structure and behavior.** Compare the supported examples and their order with the C# source, accounting for documented omissions, adaptations, and stack-specific splits. Compile or execute the runnable examples and run their tests. Check the demonstrated invariants, failure cases, and migration behavior with deterministic inputs. Report checks that could not run. Keep fixtures, environments, caches, and build output outside the skill package; verify that existing examples retain their contents.
7. **Route by task and project stack.** Update [Examples by Stack](guidelines.md#examples-by-stack) with each file's language, runtime, framework, and test-library requirements. Select examples from the affected module's actual configuration and the current task; load only the matching files within the existing budget. For a missing stack match, use shared principles and explicitly identify the gap. Check local links and record the added coverage under Changes from Upstream.

## Changes from Upstream

- Added semantic-layer diagnosis, paired policy and representation-change scenarios, and safeguards for moving reads and effects. Sources and adaptation boundaries are recorded above.
- Added focused code diagnosis for selected refactoring candidates and an explicit handoff from `sdd-architect`; this workflow is a fork addition.
- Added consumer-obligation comparison and hypothetical removal of suspected indirection to focused diagnosis, adapted from [Matt Pocock's codebase-design](https://github.com/mattpocock/skills/blob/main/skills/engineering/codebase-design/SKILL.md).
- Moved the five standalone example documents into per-topic `examples/` directories, with filenames identifying the language and relevant framework. The original C# files retain their exact contents.
- Added idiomatic Kotlin/JVM counterparts for API design, encapsulation, decomposition, evolution, and outside-in TDD, retaining the applicable C# example structure. Framework-independent, JUnit 5, and Ktor examples are separated for selective loading.
- Added Go counterparts for API design, encapsulation, decomposition, evolution, and outside-in TDD, retaining the applicable C# example structure. Go 1.22+ examples separate domain code, standard-library `testing` tests, and `net/http` / `httptest` boundaries. Adaptations explain zero-value limits, explicit errors, composition, and migration without method overloading.
- Updated example paths and added [stack-specific routing](guidelines.md#examples-by-stack), so an agent loads the example matching the project.
- Preserved the original rules, explanations, and code embedded in other documents. Kotlin and Go examples are fork additions.
- Documented conventions for adding and verifying examples for another language or stack.
