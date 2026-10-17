# Guidelines — Task Routing for `code-that-fits-in-your-head`

This is the routing layer for the skill. Find the user's task or symptom below, then load **only** the specific files listed.

**Rule of thumb**: one primary file + at most 1-2 secondary files per task. If you find yourself wanting to load four or more, re-read the task — you may be combining two tasks.

**Note on editorial content**: `agent-native/` contains four canonical amendments for code agents. Specialized agent-era additions in book-derived themes are explicitly marked and are not attributable to Seemann. See `references/agent-native/knowledge.md`.

---

## Table of Contents

- [Examples by Stack](#examples-by-stack)
- [By Task](#by-task)
- [By Symptom / Smell](#by-symptom--smell)
- [By Named Practice](#by-named-practice)
- [Agent-Native Amendments](#agent-native-amendments-not-from-the-book)

---

## Examples by Stack

When a task or workflow points to an `examples/` directory, select files using the following steps:

1. Identify the module being changed and its language/runtime from its source and build configuration. For Kotlin, inspect the relevant `build.gradle.kts`, `build.gradle`, or `pom.xml`; for C#, inspect the relevant `.csproj` and shared build configuration. Resolve framework and test-library choices from declared dependencies and existing imports. In a repository with several stacks, use the affected module's configuration.
2. Find the current task in the table below. Load its shared rules and only the example file whose requirements match that module. Follow a link to another example only when that additional topic or layer is needed; each selected file counts toward the reference-file budget above.
3. If no framework-specific file matches, use the framework-independent example for that task when available. Otherwise, use the shared rules and state the missing example coverage. Apply the project's existing stack; the examples do not prescribe new dependencies.

The table is the selection index; reading all example files is unnecessary. Kotlin entries below target the JVM. For example, a Kotlin/JVM module using Spring and JUnit 5 can use the domain and JUnit files; its HTTP tests have no Spring-specific example here.

| Current task | C# example and requirements | Kotlin/JVM example and requirements |
|---|---|---|
| API design | [C#](references/api-design/examples/csharp.md) | [Kotlin/JVM](references/api-design/examples/kotlin.md), no framework |
| Domain invariants, parsing, encapsulation | [C#, ASP.NET Core, xUnit](references/encapsulation/examples/csharp-aspnetcore-xunit.md) | [Kotlin/JVM](references/encapsulation/examples/kotlin.md), no framework |
| Parameterized invariant tests | [C#, ASP.NET Core, xUnit](references/encapsulation/examples/csharp-aspnetcore-xunit.md) | [Kotlin/JVM + JUnit 5](references/encapsulation/examples/kotlin-junit5.md) |
| Decomposition | [C# + ASP.NET Core](references/decomposition/examples/csharp-aspnetcore.md) | [Kotlin/JVM](references/decomposition/examples/kotlin.md), no framework |
| Evolution | [C# + ASP.NET Core](references/evolution/examples/csharp-aspnetcore.md) | [Kotlin/JVM](references/evolution/examples/kotlin.md), no framework |
| Unit tests, fakes, counter-cases, test spies | [C#, ASP.NET Core, xUnit](references/outside-in-tdd/examples/csharp-aspnetcore-xunit.md) | [Kotlin/JVM + JUnit 5](references/outside-in-tdd/examples/kotlin-junit5.md), examples 3, 4, 6 |
| HTTP walking skeleton, boundary tests, response postconditions | [C# + ASP.NET Core + xUnit](references/outside-in-tdd/examples/csharp-aspnetcore-xunit.md) | [Kotlin/JVM + Ktor + JUnit 5](references/outside-in-tdd/examples/kotlin-ktor-junit5.md), examples 1, 2, 5 |

The C# files retain the upstream text. The Kotlin files are additions in this fork.

---

## By Task

### Code Review

| What you're reviewing | Load these files |
|-----------------------|-------------------|
| A pull request (general) | `workflows/review-code.md`, `references/teamwork-git/checklist.md` |
| A large agent-authored migration/change | `references/agent-native/reviewability.md`, `references/agent-native/verification-loops.md` |
| Function/method complexity | `references/decomposition/rules.md`, `references/decomposition/smells.md`, `references/tooling/commands.md` |
| API surface (public interface) | `references/api-design/rules.md`, `references/api-design/examples/` |
| Naming quality | `references/api-design/rules.md` (X-Out Names section) |
| Type/class encapsulation | `references/encapsulation/rules.md`, `references/encapsulation/examples/` |
| Tests | `references/outside-in-tdd/rules.md`, `references/teamwork-git/checklist.md` |
| Commit messages | `references/teamwork-git/rules.md` (accuracy, rationale, repository policy) |
| Security posture of an endpoint | `workflows/threat-model.md`, `references/security/checklist.md` |
| Logging / cross-cutting | `references/separation-of-concerns/rules.md`, `references/separation-of-concerns/patterns.md` |

### Writing New Code

| What you're writing | Load these files |
|---------------------|-------------------|
| A brand-new feature | `workflows/add-feature-outside-in.md`, `references/outside-in-tdd/knowledge.md` |
| A new domain type with invariants | `references/encapsulation/rules.md`, `references/encapsulation/examples/` |
| A new public API | `references/api-design/knowledge.md`, `references/api-design/rules.md` |
| A unit test (first for this SUT) | `references/outside-in-tdd/rules.md`, `references/outside-in-tdd/examples/` |
| Additional test cases | `references/outside-in-tdd/rules.md` (Devil's Advocate section) |
| Cross-cutting concern (logging, caching, auth) | `references/separation-of-concerns/patterns.md` |
| A commit message | `references/teamwork-git/rules.md` |

### Refactoring

| What you're changing | Load these files |
|----------------------|-------------------|
| A long/complex function | `references/decomposition/rules.md`, `references/decomposition/patterns.md` |
| A class that has feature envy | `references/decomposition/smells.md`, `references/decomposition/examples/` |
| Splitting monolithic logic | `references/decomposition/patterns.md`, `references/separation-of-concerns/patterns.md` |
| Replacing a legacy subsystem | `references/evolution/patterns.md` (Strangler), `references/evolution/examples/` |
| Tests without touching prod code | `references/outside-in-tdd/rules.md` (separate-refactor section) |
| Hardening validation | `references/encapsulation/rules.md` (parse-don't-validate) |

### Debugging & Troubleshooting

| What you're investigating | Load these files |
|---------------------------|-------------------|
| A reproducible defect | `workflows/debug-defect.md`, `references/troubleshooting/patterns.md` |
| A flaky/non-deterministic test | `references/troubleshooting/rules.md`, `references/troubleshooting/patterns.md` |
| A regression (when did it break?) | `references/troubleshooting/patterns.md` (bisection section) |
| Slow test suite | `references/troubleshooting/rules.md` (slow tests section) |

### Security Review

| What you're threat-modelling | Load these files |
|------------------------------|-------------------|
| A new endpoint/service | `workflows/threat-model.md`, `references/security/checklist.md` |
| A STRIDE-specific concern | `references/security/rules.md` |

### Setting Up / Onboarding

| Situation | Load these files |
|-----------|-------------------|
| Starting a new code base | `references/codebase-setup/checklist.md`, `references/codebase-setup/rules.md` |
| Retrofitting discipline into a legacy base | `references/codebase-setup/rules.md` (gradual improvement section) |
| Onboarding to an unfamiliar code base | `references/code-navigation/knowledge.md`, `references/code-navigation/rules.md` |

### Evolution & Release

| Situation | Load these files |
|-----------|-------------------|
| Deploying a risky change | `references/evolution/rules.md` (feature flag section), `references/evolution/patterns.md` |
| Versioning a library / breaking change | `references/evolution/rules.md` (semver section) |
| Updating dependencies | `references/evolution/rules.md` (regular updates section) |

### Measurement & Operationalization

| Situation | Load these files |
|-----------|-------------------|
| Measure complexity, cycles, duplication, dead code, hotspots | `references/tooling/commands.md` |
| Turn a recurring finding into a lint/CI gate; persist thresholds in project memory | `workflows/operationalize-finding.md` |

---

## By Symptom / Smell

| If you notice... | Load these files |
|------------------|-------------------|
| Cyclomatic complexity > 15 or opaque branching | `references/decomposition/rules.md`, `references/decomposition/smells.md` (D1) |
| Small methods but architecture remains tangled | `references/decomposition/smells.md` (D8 system-wide sprawl) |
| Unused helpers / leftover parallel implementations | `references/decomposition/smells.md` (D9) |
| Method envies another object's data | `references/decomposition/smells.md` (D4 feature envy) |
| Vocabulary drift between layers | `references/decomposition/smells.md` (D5 lost in translation) |
| Boolean `IsValid()` scattered everywhere | `references/encapsulation/rules.md` (parse-don't-validate) |
| Invariants checked in many places | `references/encapsulation/rules.md`, `references/encapsulation/examples/` |
| `null!` or `?` sprinkled to silence compiler | `references/encapsulation/rules.md` |
| A method both returns and mutates | `references/api-design/rules.md` (CQS section) |
| Names don't carry meaning | `references/api-design/rules.md` (X-Out Names) |
| Comments explaining what code does | `references/api-design/rules.md` (naming-over-comments) |
| Logging duplicated across layers | `references/separation-of-concerns/rules.md` |
| Inheritance for cross-cutting | `references/separation-of-concerns/patterns.md` (Decorator) |
| Big-bang replacement plan | `references/evolution/patterns.md` (Strangler) |
| Live schema change | `references/evolution/patterns.md` (Expand-Contract) |
| Weak tests pass wrong code | `references/outside-in-tdd/rules.md` (Devil's Advocate + mutation testing) |
| Tests are flaky | `references/troubleshooting/rules.md`, `references/troubleshooting/patterns.md` |
| Can't reproduce a bug | `references/troubleshooting/patterns.md` (reproduce-as-test) |
| Dependency cycles between namespaces | `references/code-navigation/rules.md`, `references/tooling/commands.md` |
| Input validation after construction | `references/encapsulation/rules.md` |
| Commit history lacks rationale or useful checkpoints | `references/teamwork-git/rules.md` |
| PR sits unreviewed for days | `references/teamwork-git/rules.md` (review latency) |

---

## By Named Practice

For any retained practice referenced by name (for example Strangler or CQS), first check `references/practices-glossary/knowledge.md` for a short definition and deep-dive pointer, then load the referenced theme file.

| Practice | Deep dive |
|----------|-----------|
| Arrange-Act-Assert (AAA) | `references/outside-in-tdd/rules.md` |
| Bisection | `references/troubleshooting/patterns.md` |
| Command Query Separation (CQS) | `references/api-design/rules.md` |
| Cyclomatic Complexity | `references/decomposition/rules.md` |
| Decorator (cross-cutting) | `references/separation-of-concerns/patterns.md` |
| Devil's Advocate | `references/outside-in-tdd/rules.md`, `references/outside-in-tdd/patterns.md` |
| Expand-Contract | `references/evolution/patterns.md` |
| Feature Flag | `references/evolution/rules.md`, `references/evolution/patterns.md` |
| Functional Core, Imperative Shell | `references/decomposition/patterns.md` |
| Complementary Communication | `references/api-design/rules.md` |
| Parse, Don't Validate | `references/encapsulation/rules.md` |
| Explicit Boundary Parsing | `references/encapsulation/rules.md` |
| Red Green Refactor | `references/outside-in-tdd/rules.md` |
| Reproduce Defects as Tests | `references/troubleshooting/patterns.md` |
| Semantic Versioning | `references/evolution/rules.md` |
| Strangler | `references/evolution/patterns.md` |
| STRIDE / Threat Model | `references/security/knowledge.md`, `references/security/checklist.md` |
| Transformation Priority Premise | `references/encapsulation/rules.md` |
| X Out Names | `references/api-design/rules.md` |

Full retained list in `references/practices-glossary/knowledge.md`.

---

## Agent-Native Amendments (NOT from the book)

Load one of these when the user's concern is specifically how an agent should do something differently from Seemann's 2021 guidance. These files are editorial additions, not summaries of the book.

| Concern | File |
|---------|------|
| Verification checkpoints, independent oracles, and protection against weakened gates | `references/agent-native/verification-loops.md` |
| Invented API, version drift, package hallucination, or dependency provenance | `references/agent-native/hallucination-debugging.md` |
| Choosing practical types, schemas, tests, and executable constraints | `references/agent-native/types-as-guardrails.md` |
| Reviewing agent-authored work, including very large systematic changes | `references/agent-native/reviewability.md` |
| Overview / disclaimer that these files are not book content | `references/agent-native/knowledge.md` |

When to prefer an `agent-native/` file over a book theme:

| User's question | Book theme | Agent-native | Choose |
|-----------------|-----------|---------------|--------|
| "Why is this test flaky?" | `references/troubleshooting/` | — | Book |
| "This test has been failing since I changed library version" | `references/troubleshooting/` | `references/agent-native/hallucination-debugging.md` | Agent-native (version drift) |
| "How should this long-running change be verified?" | `references/outside-in-tdd/rules.md` | `references/agent-native/verification-loops.md` | Agent-native (checkpoint and oracle integrity) |
| "Should I enable strict mode?" | `references/codebase-setup/rules.md` | `references/agent-native/types-as-guardrails.md` | Both — strongest practical policy with a brownfield ratchet |
| "How do I write a good commit message?" | `references/teamwork-git/rules.md` | — | Book |
| "How do I keep this PR reviewable?" | `references/teamwork-git/checklist.md` | `references/agent-native/reviewability.md` | Both — book for mechanics, ours for agent-specific framing |
