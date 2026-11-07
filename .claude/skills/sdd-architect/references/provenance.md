# Method origin and vocabulary

This skill operationalizes the repository's **2026-11-07 proposal**,
`docs/decisions/research/0013-kotlin-architecture-quality-metrics/refactoring-workflow.md`.
The procedure's originating Kotlin pilot provides measured artifact kinds and
formula examples. It does not validate this skill's usefulness on real project
source or establish portable empirical thresholds. The package is self-contained;
neither the research directory nor the FPF skill is a runtime dependency.

The implementation deliberately replaces project-specific paths, Kora exclusions
and hardcoded module buckets with declared configuration. It retains support
counts, unknown states and provenance, preserves nested JVM class identities and
shows zero-internal-weight declared modules explicitly. These changes mean that
some output populations differ from the pilot; do not mix the series.

FPF informed the design through the following contributions, expressed in ordinary
engineering terms rather than requiring a framework-specific report:

- C.16.MR: recover the subject, formula, population and collection conditions.
- C.16.IR: identify different explanations compatible with one indication.
- C.31: assess change locality, information hiding and dependency direction.
- C.11.CRC: compare a feasible change with the actual current system, including
  cost, prerequisites and overlapping benefits.
- C.11.DUA: ask for evidence only when its attainable answer can change the choice.
- C.43: return realized outcomes to diagnosis and revise mistaken expectations.

FPF: Anatoly Levenchuk, [First Principles Framework](https://github.com/ailev/FPF),
the source procedure used the local adaptation at commit
`f0ccf42c97361d6e95fa39bea22fb000d831549f`. No specification text is bundled here.

## Vocabulary used in this package

| Term | Meaning |
| --- | --- |
| Snapshot | Source identity, selected scope and immutable raw measurement artifacts |
| Architectural module | Declared package group with responsibility, public contract and dependency rules |
| Candidate | A subject selected for source investigation by signals or a known change scenario |
| Signal | An observed metric and its allowed evidential role; not a diagnosis |
| Recommendation | One feasible complete change addressing one established cause |
| Priority group | Recommendations indistinguishable by the supported M/R/S effect profile |
| Execution order | Prerequisite-respecting work order, distinct from benefit priority |

## Instrument definitions

- [JDK jdeps](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jdeps.html):
  class dependency analysis and archive-filter behavior.
- [detekt 1.23.8 complexity rules](https://detekt.dev/docs/1.23.8/rules/complexity/):
  instrument-specific rule definitions; parsers retain unknown values for unsupported messages.
- [JaCoCo counters](https://www.jacoco.org/jacoco/trunk/doc/counters.html):
  bytecode coverage semantics and exception-handler limitation.
- [Code Maat logical coupling](https://github.com/adamtornhill/code-maat/blob/master/src/code_maat/analysis/logical_coupling.clj):
  symmetric coupling; exact support is retained by this implementation.
- [ArchUnit package dependency checks](https://www.archunit.org/userguide/html/000_Index.html#_package_dependency_checks)
  and [Kotlin visibility](https://kotlinlang.org/docs/visibility-modifiers.html):
  acceptance checks for declared boundaries.

Synthetic calculation and behavior checks qualify the supplied mechanics. A project
owner still needs to assess diagnosis usefulness and intervention feasibility on
real Kotlin sources; future benefits need post-implementation observation.
