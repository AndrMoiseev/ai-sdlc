---
name: sdd-code-design
description: Apply shared and project heuristics to software design and review. Assess review feedback for reuse and compare project heuristics with shared guidance. Use when the user explicitly invokes sdd-code-design or an active skill explicitly calls it. Do not use for coding or review on task relevance alone.
disable-model-invocation: true
---

# SDD Code Design

Engineering heuristics for sustainable software, based on Mark Seemann's 2021 book and clearly labelled agent-era amendments.

The bundled rules are language-neutral. Select C#, Kotlin/JVM or Go examples by the affected module's stack using `guidelines.md`. Projects can contribute heuristics for their own conditions.

## Philosophy (Why This Skill Exists)

Software development is principally a **design activity**, not construction. An agent may produce most of the text, but people still review, operate, extend, and own the resulting system. These heuristics make software sustainable: understandable, resistant to architectural erosion, and cheap to change after thousands of decisions.

Core mental model from Chapter 1:

| Metaphor | What it gets right | What it misses |
|----------|-------------------|-----------------|
| **Building a house** | Plans, structure | Software endures; there's no construction phase (compiling is free); dependencies can start anywhere |
| **Growing a garden** | Pruning, refactoring, tending | Code does not improve by itself; generated code still needs stewardship |
| **Art / craft** | Skill, mastery, situational knowledge | Doesn't scale; leaves newcomers without guidance |
| **Engineering** (the target) | Heuristics, review, sign-off, checklists | We're not there yet — physical-construction calculations don't apply |

> "The act of describing a program in unambiguous detail and the act of programming are one and the same." — Kevlin Henney

**Practical implications for a code agent:**

1. **Successful software endures.** Prefer changes that preserve clear boundaries and keep future change affordable.
2. **Complexity is the enemy, not task size.** Agents can complete changes spanning tens of thousands of lines when architecture, plan, and acceptance criteria are sound. Reject needless coupling, duplication, hidden effects, and unverifiable bulk—not large scope by itself.
3. **Heuristics, not laws.** Understand the purpose of a rule before applying or relaxing it. Project policy overrides generic formatting and workflow conventions.
4. **Verification is part of design.** Types, tests, schemas, architecture checks, observability, and explicit acceptance criteria constrain both human- and agent-written code.
5. **Code is a liability.** Generated volume is not progress. Prefer the smallest coherent design that solves the problem without accumulating debt.

See `references/foundations/` for more on sustainability, readability, and brain-limited design.

## Invocation

Apply this skill when the user explicitly invokes it or an active skill explicitly instructs you to invoke `sdd-code-design` for the current task. Follow the calling skill's requested scope. Task relevance, a catalog entry, or a passing mention of the skill is not an invocation; do not select it implicitly.

For an explicit call from a sibling APM skill, read `../sdd-code-design/SKILL.md` relative to the calling skill's directory and apply it within the requested scope. Resolve this skill's references relative to its own directory. This file-based call does not require automatic skill selection or the Skill tool.

## How to Use This Skill

1. Identify the requested decision and scope. Use [guidelines](guidelines.md) to select the workflow and bundled references by task or symptom.
2. When designing, implementing or assessing code, check `memory/code-design/heuristics.md` at the **target project's root**. If present, use relevant inline entries or follow only the group links whose situation matches the current decision. If absent, proceed with the bundled guidance.
3. Apply each heuristic within its stated conditions. If local and shared guidance point to different choices, check whether the project exception applies. Requirements and acceptance criteria govern the decision. Use `references/practices-glossary/` for named practices and cross-references.
4. Use project memory as a read-only source during ordinary work. A focused diagnosis returns findings to its caller.

## Chapter Index

| Topic | Use when... |
|-------|-------------|
| `references/foundations/` | Sustainability, readability, complexity control, and code as liability |
| `references/codebase-setup/` | Starting or inheriting a code base — git, build automation, warnings-as-errors |
| `references/outside-in-tdd/` | Writing new features test-first; walking skeleton, AAA, triangulation, devil's advocate, editing tests |
| `references/encapsulation/` | Designing types with invariants; DTO vs Domain Model, always-valid, Postel's law, parse-don't-validate |
| `references/decomposition/` | Method and system complexity; cyclomatic complexity, cohesion, coupling, feature envy, fractal architecture, semantic layers, and effect ordering |
| `references/api-design/` | Designing a public API; affordance, poka-yoke, CQS, hierarchy of communication, naming over comments |
| `references/separation-of-concerns/` | Adding cross-cutting concerns; Decorator pattern, logging, what to log, performance vs legibility |
| `references/teamwork-git/` | Writing commits, reviewing changes, continuous integration, collective ownership |
| `references/evolution/` | Changing running systems; feature flags, Strangler pattern, versioning, regular dependency updates, Conway's law |
| `references/troubleshooting/` | Debugging a defect; scientific method, rubber ducking, reproduce-as-test, bisection, non-deterministic defects |
| `references/security/` | Threat modelling; STRIDE (spoofing, tampering, repudiation, info disclosure, DoS, elevation) |
| `references/code-navigation/` | Onboarding to a code base; big picture, file organisation, cycles, property-based testing, behavioural code analysis |
| `references/tooling/` | Executable measurement commands: complexity, cycles, duplication, dead code, hotspots, mutation testing |
| `references/practices-glossary/` | Looking up a named design practice and its current status |

### ⚠️ Editorial amendments (NOT from the book)

The folder below is NOT content from Seemann's book. It contains our own additions covering agent-specific concerns the 2021 book does not address. Do not attribute these files to Seemann. See `references/agent-native/knowledge.md`.

| Topic | Use when... |
|-------|-------------|
| `references/agent-native/` | Agent-specific verification integrity, hallucination and dependency grounding, executable guardrails, and accountable review |

## Workflows

Composite step-by-step processes live in `workflows/`:

| Task | Workflow |
|------|----------|
| Diagnose a proposed design or implemented code within a named scope | [Focused diagnosis](workflows/diagnose-code.md) |
| Assess a review comment, record its agreed lesson, or compare project heuristics with shared guidance | [Maintain project heuristics](workflows/maintain-project-heuristics.md) |
| Review a pull request / piece of code | `workflows/review-code.md` |
| Design or implement a new or changed feature | [Outside-in](workflows/add-feature-outside-in.md), selecting the work product |
| Design or implement a structural change with preserved behavior | [Refactoring](workflows/refactor-code.md), selecting the work product |
| Investigate and fix a defect | `workflows/debug-defect.md` |
| Threat-model a new endpoint | `workflows/threat-model.md` |
| Enforce a stable, mechanically checkable rule and document its verification command | [Operationalize a finding](workflows/operationalize-finding.md) |

See `guidelines.md` for the full routing layer (task → file, symptom → file).
