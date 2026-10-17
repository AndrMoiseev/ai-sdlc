# code-that-fits-in-your-head

This skill is a fork of [CodeAlive-AI's original skill](https://github.com/CodeAlive-AI/ai-driven-development/tree/main/skills/code-that-fits-in-your-head), imported from commit [`79d911b`](https://github.com/CodeAlive-AI/ai-driven-development/commit/79d911b773d83986bee7ac4170d09a972e61fe31). Changes from upstream are listed below.

Cross-agent skill for keeping software understandable and inexpensive to change. It helps prevent accidental complexity, architectural erosion into a Big Ball of Mud, and silent technical-debt accumulation—especially when coding agents can generate code faster than people can review and own it.

The skill is based on Mark Seemann's *Code That Fits in Your Head: Heuristics for Software Engineering* (2021), with clearly labelled editorial amendments for agent-driven development.

Use it when a task is about:

- designing complex code, APIs, domain types, validation boundaries, and invariants
- decomposing tangled functions, classes, workflows, or subsystems
- reviewing code for readability, cohesion, coupling, encapsulation, and testability
- adding features outside-in with tests and a walking skeleton
- debugging defects with reproducible tests, bisection, and tighter verification loops
- evolving legacy systems with feature flags, Strangler-style migration, reversible stages, and explicit verification
- threat-modelling endpoints or services with STRIDE
- reviewing agent-generated changes for architectural fit, verification integrity, dependency provenance, and new debt

Large tasks are not rejected because they are large. Agents can successfully implement changes spanning tens of thousands of lines when the work has coherent architecture, a clear plan, trustworthy acceptance criteria, and verifiable checkpoints. The skill targets unstructured complexity and unverifiable change—not scope by itself.

## How It Works

`SKILL.md` contains the trigger description and top-level index. `guidelines.md` is the routing layer: it maps tasks, symptoms, and named practices to the smallest useful reference files.

Code examples are C#-first; every rule and the tooling tables are language-neutral.

The skill uses progressive disclosure. Load one primary file and at most one or two secondary files for the current task instead of reading the whole skill. When a rule proves repeatedly useful in a repository, operationalize it (`workflows/operationalize-finding.md`) so it persists as a gate and in project agent instructions.

## Structure

```text
SKILL.md                 # Trigger, philosophy, chapter index
guidelines.md            # Task/symptom/practice routing
workflows/               # Step-by-step workflows for common engineering tasks
references/              # Focused reference packs by theme
references/tooling/      # Executable measurement commands (complexity, cycles, dead code, …)
```

Core themes include decomposition, encapsulation, API design, outside-in TDD, separation of concerns, teamwork and Git discipline, software evolution, troubleshooting, security, and measurement tooling. Workflows cover review, outside-in features, debugging, threat modelling, and operationalizing findings into gates.

## Source Boundaries

Most reference folders summarize or operationalize ideas from Seemann's book. The `references/agent-native/` folder is different: it contains local editorial additions for coding agents—verification integrity, hallucination and dependency grounding, executable guardrails, and accountable review. Editorial amendments placed in book-derived themes are explicitly marked. Do not attribute them to Seemann.

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

- Moved the five standalone example documents into per-topic `examples/` directories, with filenames identifying the language and relevant framework. The original C# files retain their exact contents.
- Added idiomatic Kotlin/JVM counterparts for API design, encapsulation, decomposition, evolution, and outside-in TDD, retaining the applicable C# example structure. Framework-independent, JUnit 5, and Ktor examples are separated for selective loading.
- Updated example paths and added [stack-specific routing](guidelines.md#examples-by-stack), so an agent loads the example matching the project.
- Preserved the original rules, explanations, and code embedded in other documents. Kotlin examples are fork additions.
- Documented conventions for adding and verifying examples for another language or stack.
