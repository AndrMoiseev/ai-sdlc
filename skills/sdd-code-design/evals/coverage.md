# Heuristic coverage

Use the references below to find the relevant task and its scored behavior in the [scenario bank](evals.json). A reference such as `18.3` identifies case 18, expectation 3 in its `expectations` array. In that example the answer must preserve the read/publish order when publishing fails. A design that merely extracts a pure calculation cannot earn that point.

The inventory includes 117 numbered chapter rules, all 81 entries under chapter *Guidelines* and *Exceptions*, and the agent-specific guidance. Additional rows index decisions unique to patterns, workflows and project memory. The practices glossary and measurement techniques point to the same scored decisions where appropriate. Worked examples in different languages and repeated quick-reference/checklist summaries use their canonical rule. A source row records where a behavior is tested. Scores and run counts belong to the individual scenarios.

- [Chapter rules](#chapter-rules)
- [Agent-specific guidance](#agent-specific-guidance)
- [Practices and measurements](#practices-and-measurements)
- [Workflows and project heuristics](#workflows-and-project-heuristics)

## Chapter rules

### Foundations Rules

[references/foundations/rules.md](../references/foundations/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Write for the Next Reader and Changer | `9.1` |
| 2. Keep Each Unit Conceptually Cohesive | `17.1` |
| 3. Make Context Discoverable and Effects Explicit | `9.2` |
| 4. Treat Code as a Liability, Not an Asset | `2.2`, `9.1`, `33.5` |
| 5. Optimize for Sustainability | `9.3`, `9.4` |
| 6. Deliberate Before Accepting, Not Before Generating | `43.1` |
| Recording Debt | `9.3`, `47.4` |
| Default Thresholds and project overrides | `9.1`, `17.1`, `24.3`, `30.5`, `44.3` |
| Guideline 1 · Prefer established libraries over reinventing solved infrastructure. | `50.2` |
| Guideline 2 · Re-check conclusions that look obvious but depend on hidden assumptions. | `58.1` |
| Guideline 3 · Prefer written, versioned rationale over transient conversation for important decisions. | `50.3` |
| Guideline 4 · Keep terminology consistent across code, tests, documentation, and product language. | `50.3` |
| Exception 1 · Exploratory spike: readability may be relaxed only when the spike is isolated and will be discarded or deliberately rewritten. | `50.1` |
| Exception 2 · Fixed external contract: awkward shapes may be unavoidable at a boundary; translate them into cleaner internal types. | `50.2`, `52.1` |
| Exception 3 · Production emergency: accept temporary debt only with explicit follow-up, owner, and verification of the narrow fix. | `55.1` |

### Codebase Setup Rules

[references/codebase-setup/rules.md](../references/codebase-setup/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Use Git From Line 1 | `10.1` |
| 2. Automate the Build From Line 1 | `10.2` |
| 3. Turn On All Error Messages (Warnings as Errors) | `10.3` |
| 4. Build the Deployment Pipeline Early | `10.4` |
| 5. Apply the Gradual Ratchet to Legacy Code Bases | `11.1`, `44.2` |
| 6. Use Automated Gates as Cultural Armour | `4.1`, `11.2` |
| Guideline 1 · Prefer reproducible, non-interactive commands for operations that CI and agents must run. Human interface choice is secondary. | `10.2` |
| Guideline 2 · Read the online documentation for each analyser rule before suppressing it — most rules encode decades of accumulated knowledge. | `11.2` |
| Guideline 3 · Don't show screenshots or step-by-step GUI instructions in documentation; they go stale fast. | `10.5` |
| Exception 1 · Truly ephemeral code: A throwaway script you will delete within a week can skip `git init`. The threshold should still be low. | `50.1` |
| Exception 2 · Large legacy migrations: Don't block all work to reach zero warnings — follow the gradual ratchet instead. | `11.1` |
| Exception 3 · Known-bad false positive in analyser: Suppress the specific rule at the specific site, with a comment explaining why. Do not disable the analyser globally. | `11.2` |
| Pin toolchain versions and lockfiles for reproducible builds | `10.2` |

### Outside-In TDD Rules

[references/outside-in-tdd/rules.md](../references/outside-in-tdd/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Make Arrange / Act / Assert Visually Clear | `6.1`, `6.2`, `6.3`, `51.1` |
| 2. Start at the Boundary, Work Inward | `5.4`, `8.1`, `8.2`, `12.1` |
| 3. See Every Test Fail Before You Trust It | `6.4`, `12.3`, `14.3` |
| 4. Start With Stable Boundary Assertions; Strengthen Before Acceptance | `8.3`, `8.4`, `12.2` |
| 5. Preserve Test Intent When Modifying Tests | `14.1` |
| 6. Make Oracle Changes Auditable | `14.2` |
| 7. Apply Useful Static Analysis to Test Code | `11.3` |
| 8. Use Devil's Advocate to Decide When You Need Another Test | `13.1` |
| 9. Switch from Devil's Advocate to Red-Green-Refactor Once Structure Exists | `13.2` |
| 10. Separate DTO from Domain Model | `15.1` |
| Deciding You Have Enough Tests | `13.4` |
| Guideline 1 · Aim for balance between arrange / act / assert sections. A 2-2-2 or 1-1-1 shape reads better than 5-1-1. | `51.1` |
| Guideline 2 · When an act section is a single line hidden behind a lot of setup, extract a SUT Encapsulation Method or Test Utility Method in the test project. | `51.1` |
| Guideline 3 · Write down edge cases you think of while writing a test — don't derail to implement them mid-test. | `51.4` |
| Guideline 4 · Commit after each passing test run; consider pushing through the deployment pipeline. | `51.4` |
| Guideline 5 · Prefer Value Objects in the Domain Model — structural equality makes elegant `Assert.Contains(expected, actual)` possible. | `51.2` |
| Exception 1 · Characterisation tests: No red phase by definition. Assert only the weakest stable property of the existing code. | `48.1` |
| Exception 2 · Humble Objects (SQL repositories, framework glue): May skip unit tests; push logic out and cover them with integration tests later. | `51.3` |
| Exception 3 · Auto-generated code (IDE-generated `Equals`, `GetHashCode`, constructors): Trust the generator; no need to triangulate. | `51.2` |
| Pair self-authored checks with an independent oracle and preserve verification | `14.1`, `14.4` |

### Encapsulation Rules

[references/encapsulation/rules.md](../references/encapsulation/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. A Domain Object Must Never Exist in an Invalid State | `16.1`, `16.3` |
| 2. Validate at Construction, Not at Each Call Site | `15.2`, `16.1` |
| 3. Parse, Don't Validate | `15.2` |
| 4. Be Explicit at Boundaries: Accept Supported Compatibility, Reject the Rest | `15.3` |
| 5. Throw `ArgumentNullException`, Not `NullReferenceException` | `15.4` |
| 6. Return 400 Bad Request for Invalid HTTP Input | `15.3` |
| 7. Separate DTO from Domain Model | `15.1` |
| 8. Drive Invariants with Parametrised Tests | `16.2` |
| 9. Move in Verified Transformations (TPP) | `13.3` |
| Guideline 1 · Prefer a dedicated type (e.g. `NaturalNumber`) over a raw `int` when an invariant applies across many methods. | `16.1` |
| Guideline 2 · If your language lacks nullable reference types, use a `Maybe<T>` / `Option<T>` container instead of `null`. | `52.2` |
| Guideline 3 · Don't assert on exception messages — the message is not part of behaviour; coupling tests to it causes needless churn. | `52.4` |
| Guideline 4 · Follow Red → Green → Refactor: after every green, ask "can I simplify this?". | `13.2` |
| Exception 1 · Legacy boundaries: When wrapping a legacy API that already returns half-validated data, a transitional adapter with looser invariants may be justified. | `52.1` |
| Exception 2 · Internal-only types: If a type is only ever constructed from already-validated data within a single module, its guards can be lighter — but document this. | `52.3` |
| Exception 3 · Performance-critical hot paths: Where measured profiling shows guard clauses dominate, consider moving validation to the boundary only. This is rare. | `52.3` |

### Decomposition Rules

[references/decomposition/rules.md](../references/decomposition/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Review Cyclomatic Complexity Above 15 | `17.1` |
| 2. Split by Responsibility, Not Display Geometry | `17.2` |
| 3. Watch Interacting State | `17.2` |
| 4. Prefer Sequential Composition to Hidden Nesting | `18.1` |
| 5. Favour a Pure Core and Explicit Effects | `18.2` |
| 6. Move Behaviour to the Data It Understands | `17.3` |
| 7. Extract Low-Coupling Sections First | `17.4` |
| 8. Parse Into Stronger Types | `15.2` |
| 9. Preserve Coherence at Every Zoom Level | `19.1`, `19.4` |
| 10. Check System Complexity, Not Only Methods | `33.1`, `33.4` |
| 11. Compare Consumer Obligations Before and After | `1.2`, `2.3`, `3.1`, `3.2`, `5.1`, `5.2`, `5.3`, `19.2` |
| 12. Mentally Remove a Suspected Indirection | `1.1`, `1.3`, `2.1`, `2.2`, `2.4`, `3.3`, `3.4`, `48.3` |
| Guideline 1 · Prefer deletion and reuse over adding another helper or abstraction. | `9.1` |
| Guideline 2 · Constructors should not perform hidden I/O or irreversible effects. | `18.1` |
| Guideline 3 · Treat `static` helpers and utility modules as smells when they collect unrelated behavior. | `17.5` |
| Guideline 4 · Use blank-line groupings as clues to responsibility boundaries, not as proof that extraction is needed. | `17.5` |
| Guideline 5 · Refactor when a metric and the code's semantics both indicate rising change cost. | `17.1` |
| Exception 1 · Cohesive algorithms and generated code may be long or branch-heavy while still being the clearest representation. | `17.1` |
| Exception 2 · System edges coordinate effects; keep the sequence explicit rather than forcing artificial purity. | `18.2` |
| Exception 3 · Production emergencies may accept temporary complexity with a recorded owner and removal condition. | `55.1` |
| Exception 4 · Project policy may set different metric thresholds; preserve the underlying goal of comprehensibility and local change. | `17.1` |

### API Design Rules

[references/api-design/rules.md](../references/api-design/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Every Method Is a Command OR a Query — Never Both | `20.1`, `20.3` |
| 2. Prefer Queries Over Commands | `20.2` |
| 3. Make Illegal States Unrepresentable (Poka-Yoke) | `21.1` |
| 4. Advertise Contracts With Types, Not Just Names | `21.1` |
| 5. Favor Well-Named Methods Over Comments | `21.3` |
| 6. Apply the X-Out Names Exercise | `21.2` |
| 7. Use Complementary Communication Channels | `21.3`, `21.5` |
| 8. Design for the Reader, Not the Writer | `9.1`, `20.4`, `21.4` |
| 9. Avoid Swiss Army Knives | `21.4` |
| Guideline 1 · Prefer non-nullable reference types; use `?` only when `null` is genuinely a valid value | `53.1` |
| Guideline 2 · Evaluate a constructor from its signature alone: required inputs and invalid combinations should be clear | `53.1` |
| Guideline 3 · When in doubt, write a test that tries to misuse the API — if it is too easy, tighten the types | `53.3` |
| Guideline 4 · If a class owns configuration, pass the whole class as a dependency rather than exploding its fields | `53.1` |
| Exception 1 · Legacy databases or transports: You may have to return generated IDs from an insert. This is solvable within CQS but sometimes framework constraints force pragmatic violations. | `20.3`, `53.4` |
| Exception 2 · Cross-boundary DTOs: Configuration objects populated from JSON or environment files often have anemic encapsulation by necessity. | `15.1`, `53.2` |
| Exception 3 · Performance-critical paths: Occasionally a combined Command+Query is justified; document the why and isolate it. | `53.4` |

### Separation of Concerns Rules

[references/separation-of-concerns/rules.md](../references/separation-of-concerns/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Attach Cross-Cutting Concerns at an Explicit Seam | `22.1`, `23.3` |
| 2. Log what you cannot reproduce | `22.2`, `54.1` |
| 3. Do not double-log application-level events | `22.2` |
| 4. Log unhandled exceptions; treat each as a defect | `22.3` |
| 5. Use structured logging | `22.4`, `64.1` |
| 6. Prefer legibility over micro-optimisation | `23.1` |
| 7. Only optimise proven bottlenecks | `23.2`, `23.4` |
| Guideline 1 · Redact sensitive fields before logging (JWTs, passwords, card numbers). | `22.4` |
| Guideline 2 · One Decorator, one concern. Do not stack logging + caching + retries into one class. | `54.2` |
| Guideline 3 · Put Decorator wiring in composition root (DI registration), not in the domain. | `54.2` |
| Guideline 4 · When the framework offers a built-in cross-cutting feature (e.g. authentication middleware), prefer it over a home-grown Decorator. | `54.2` |
| Exception 1 · Legacy code with intertwined pure/impure logic: You may have to log everything until the code is refactored. | `54.1` |
| Exception 2 · Tight inner loops with measured bottlenecks: Profile-backed micro-optimisation is legitimate here, but comment the "why" and keep the unoptimised version nearby. | `54.3` |
| Exception 3 · Framework-level cross-cutting concerns (security, CORS): Built-in middleware is usually better than a custom Decorator. | `54.2` |
| Enforce structured fields and redaction mechanically | `64.1` |
| Review I/O changes for missing or duplicated telemetry | `64.2` |
| Use traces/metrics for timing and logs for discrete events | `64.2` |
| Avoid method-entry/exit logging of pure domain functions | `64.3` |
| Specify cache invalidation or a staleness contract with the cache | `23.3` |

### Teamwork and Git Rules

[references/teamwork-git/rules.md](../references/teamwork-git/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Write Accurate, Searchable Commit Messages | `24.1` |
| 2. Preserve Useful Working History | `24.2` |
| 3. Integrate Frequently Enough to Control Divergence | `24.3` |
| 4. Keep Each Review Architecturally Coherent | `24.2`, `25.1` |
| 5. Review Independently | `24.4`, `25.2`, `63.4` |
| 6. Preserve Human Ownership Where It Matters | `25.2` |
| 7. Make Rejection Actionable | `25.3` |
| 8. Protect the Integrity of Tests and Gates | `14.2`, `25.3` |
| Guideline 1 · Keep published history coherent and useful for bisection and recovery. | `24.2` |
| Guideline 2 · Automate formatting and other objective style policy rather than spending human review on it. | `44.4` |
| Guideline 3 · Rotate human ownership across important areas to reduce knowledge silos. | `55.3` |
| Guideline 4 · Run the change locally or in an isolated environment when risk warrants it. | `55.4` |
| Guideline 5 · Prefer asynchronous written rationale for durable decisions; use synchronous collaboration when ambiguity is cheaper to resolve together. | `55.4` |
| Exception 1 · Ephemeral code may not need durable history or formal review. | `50.1` |
| Exception 2 · Solo work cannot create a second human owner; compensate with stronger automated evidence and deliberate later review for material risk. | `55.1` |
| Exception 3 · Emergency response may merge through an expedited lane with explicit follow-up and post-change review. | `55.1` |

### Evolution Rules

[references/evolution/rules.md](../references/evolution/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Use Feature Flags to Split Deploy from Release | `26.1` |
| 2. Remove Feature Flags After the Release Lands | `26.3`, `26.4` |
| 3. Replace Subsystems with the Strangler Pattern | `27.1`, `27.2`, `27.3`, `27.4` |
| 4. Use Semantic Versioning for Anything Others Depend On | `28.1`, `57.2` |
| 5. Give Users Advance Warning of Deprecations | `28.2` |
| 6. Update Dependencies on a Schedule | `28.3`, `28.4` |
| 7. Be Aware of Conway's Law When Designing | `29.1`, `29.2` |
| Guideline 1 · Prefer *weakening preconditions* over adding overloads when strangling a method. A range-of-dates reader can subsume a single-date reader; the reverse is not true. | `27.1` |
| Guideline 2 · When you add a method to an interface, add it to every implementer in the same commit so the build stays green. | `27.1` |
| Guideline 3 · Bundle multiple small breaking changes into one major release if that reduces caller pain — but not if each change forces massive rework on its own. | `57.1` |
| Guideline 4 · Prefer avoiding breaking changes altogether. Stable libraries can live on the same major version for years. | `57.2` |
| Exception 1 · Monolith with no external API: Breakage is cheap, so you can be less strict about SemVer. Still think in those terms for your own clarity. | `57.3` |
| Exception 2 · Narrow, easily verified change: In-place editing is fine when blast radius and rollback are clear; Strangler would add needless machinery. | `27.4` |
| Exception 3 · Emergency CVE: Update the vulnerable dependency immediately, out of rhythm. | `28.3` |

### Troubleshooting Rules

[references/troubleshooting/rules.md](../references/troubleshooting/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Understand Before You Fix | `30.1` |
| 2. Record a Falsifiable Hypothesis | `30.1`, `31.3` |
| 3. Reproduce the Defect With an Executable Check | `30.2`, `31.3` |
| 4. Externalize Reasoning Before Escalation | `30.4`, `31.4` |
| 5. Try Removing Complexity Before Adding a Special Case | `30.3` |
| 6. Keep Feedback Fast Enough to Use Reliably | `30.5` |
| 7. Isolate Non-Determinism Before Fixing It | `31.1` |
| 8. Use History When the Behavior Changed | `31.2` |
| 9. Stop Repeating Experiments Without New Evidence | `30.3`, `31.4` |
| Guideline 1 · Prefer observable experiments over debugger-only conclusions that leave no regression guard. | `58.2` |
| Guideline 2 · Preserve logs, failing inputs, versions, and environment needed to reproduce the issue. | `31.4` |
| Guideline 3 · Use stronger domain types to prevent silent argument swaps and invalid states. | `58.3` |
| Guideline 4 · When bisection identifies the cause, still add the appropriate regression guard. | `31.3` |
| Guideline 5 · State explicitly when the correct action is no code change. | `58.1` |
| Exception 1 · Exploration without a harness may begin with REPL commands or ad-hoc scripts; turn a stable reproduction into a durable check before accepting the fix. | `58.2` |
| Exception 2 · Rare races may require architectural containment or production instrumentation rather than a deterministic local test. | `31.4` |
| Exception 3 · Emergency mitigation may precede full diagnosis when harm is ongoing; preserve evidence and perform root-cause analysis afterwards. | `55.2` |

### Code Navigation Rules

[references/code-navigation/rules.md](../references/code-navigation/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Start at the entry point, then zoom in | `32.1` |
| 2. Navigate with search, imports, tests, and history | `32.1`, `32.2` |
| 3. Read tests first — they encode intent | `32.2` |
| 4. Treat hard-to-write tests as a design smell | `32.3` |
| 5. Check for dependency cycles early | `33.1` |
| 6. A monolith is not automatically wrong | `29.3`, `33.2` |
| 7. Use property-based testing for invariants | `34.1`, `34.2`, `34.3` |
| 8. Use behavioural code analysis on legacy bases | `33.3` |
| Context Budget | `32.1`, `32.4`, `56.4` |
| Guideline 1 · Follow the repository's existing file-organisation convention; flat vs deep is a project choice | `56.1` |
| Guideline 2 · When a test helper has no test-specific logic, consider moving it to a production client SDK | `56.3` |
| Guideline 3 · Use numerical thresholds from behavioural analysis to direct attention, not as law | `33.3` |
| Guideline 4 · On a larger team, use knowledge maps (main author per file) to find bus-factor risk | `55.3` |
| Exception 1 · Framework conventions: If a framework expects a specific folder layout (e.g. Next.js `app/`, Rails MVC), follow it — fighting conventions costs more than it saves | `56.1` |
| Exception 2 · Regulatory splits: Some compliance regimes require package-level isolation regardless of coupling | `56.2` |
| Exception 3 · Tiny repositories: Progressive disclosure still helps, but a full read may fit the budget | `56.4` |

### Security Rules

[references/security/rules.md](../references/security/rules.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Spoofing · 1. Require authentication for anything that matters | `35.1` |
| Spoofing · 2. Use established identity providers | `35.2` |
| Spoofing · 3. Keep the decision to require auth at the endpoint | `35.1` |
| Tampering · 1. Always use parameterised queries | `39.1` |
| Tampering · 2. Require HTTPS; do not make TLS optional | `36.2` |
| Tampering · 3. Never trust client-side state | `35.3` |
| Tampering · 4. Use opaque, high-entropy resource identifiers | `36.1` |
| Repudiation · 1. Log every state-changing action with an attributable identity | `37.1` |
| Repudiation · 2. Make audit logs tamper-evident | `37.2` |
| Repudiation · 3. Do not let a user deny a recorded action without evidence | `37.3` |
| Repudiation · 4. Balance friction against value | `37.4` |
| Information Disclosure · 1. Minimise what you expose | `35.4` |
| Information Disclosure · 2. Require authentication for any endpoint that returns PII or sensitive data | `35.4` |
| Information Disclosure · 3. Do not log secrets | `22.4`, `36.3` |
| Information Disclosure · 4. Be explicit about PII | `36.3` |
| Information Disclosure · 5. Treat sensitive URLs as secrets | `36.1`, `36.4` |
| Denial of Service · 1. Rate-limit public endpoints | `38.1` |
| Denial of Service · 2. Set timeouts on every outbound call | `38.2` |
| Denial of Service · 3. Cap payload sizes and collection lengths | `38.2` |
| Denial of Service · 4. Prefer managed languages for new services | `38.3` |
| Denial of Service · 5. For write-heavy spike workloads, consider CQRS | `38.4` |
| Elevation of Privilege · 1. Principle of least privilege | `39.2` |
| Elevation of Privilege · 2. Do not run as root / administrator | `39.3` |
| Elevation of Privilege · 3. Separate authentication from authorisation | `35.3` |
| Elevation of Privilege · 4. Close SQL injection paths (again) | `39.1` |
| Elevation of Privilege · 5. Disable dangerous stored procedures | `39.4` |
| Prompt and Goal Manipulation | `40.1` |
| Tool and Credential Least Privilege | `40.2` |
| Dependency and Supply-Chain Integrity | `40.3` |
| Destructive and External Actions | `40.1`, `40.4` |
| Verification Ownership | `25.2`, `40.5` |

## Agent-specific guidance

### Verification Integrity (Agent-Native)

[references/agent-native/verification-loops.md](../references/agent-native/verification-loops.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Verify coherent checkpoints, not only the final result | `43.1`, `47.2` |
| 2. Use the repository's canonical commands | `11.4`, `43.4`, `44.3` |
| 3. Do not weaken verification to obtain green output | `14.1` |
| 4. Require an independent oracle for material risk | `7.1`, `7.3`, `14.4`, `43.2` |
| 5. Record evidence | `7.4`, `25.4`, `43.4` |
| 6. Preserve recovery points | `25.5`, `43.5`, `47.3` |
| 7. Stop on contradictory evidence | `43.3` |
| Feedback Layers and Independent Oracles | `34.2`, `41.4`, `43.4` |

### Hallucination Debugging (Agent-Native)

[references/agent-native/hallucination-debugging.md](../references/agent-native/hallucination-debugging.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Grep-before-use | `42.1` |
| 2. Read-before-edit | `42.1` |
| 3. Typecheck-before-commit | `42.2`, `60.4` |
| 4. Docs-for-this-version, not docs-in-general | `42.1`, `60.2` |
| 5. When uncertain, run it | `42.3` |
| 6. Schema-validate all external responses | `7.2`, `42.4`, `60.3` |
| 7. Verify before adding a dependency | `28.4`, `40.3`, `42.5` |
| Detection and debugging workflow | `42.1`, `42.3`, `60.1` |
| Common Hallucination Classes and Detection | `60.1`, `60.2`, `60.3`, `60.4` |

### Executable Guardrails (Agent-Native)

[references/agent-native/types-as-guardrails.md](../references/agent-native/types-as-guardrails.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| 1. Use the strongest practical constraints for the repository | `11.1`, `41.1` |
| 2. Type public and cross-module contracts | `16.4`, `21.1`, `41.2` |
| 3. Parse external data into stronger internal types | `15.2`, `41.2` |
| 4. Prefer domain types over primitive conventions | `16.1`, `41.2` |
| 5. Keep examples executable when they define behavior | `21.5`, `41.3` |
| 6. Fail closed at trust and security boundaries | `15.3`, `41.2` |
| 7. Do not suppress a guardrail merely to unblock generation | `11.2`, `44.2` |
| 8. Pair self-authored tests with independent evidence for material changes | `7.1`, `40.5`, `43.2` |
| Choosing a Stack | `41.1` |

### Accountable Review (Agent-Native)

[references/agent-native/reviewability.md](../references/agent-native/reviewability.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Large Changes | `25.1` |
| Review Contract | `25.4`, `25.5` |
| Risk Lanes | `25.2`, `63.1` |
| What to Review First and Red Flags | `25.3` |
| Mechanical, routine and material changes | `63.1`, `63.2`, `63.3` |

## Practices and measurements

### Decomposition Patterns

[references/decomposition/patterns.md](../references/decomposition/patterns.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Preserve behavior when moving effects | `18.3` |
| Sequential Composition | `18.1` |
| Nested Composition (Use Sparingly) | `18.1` |
| Functional Core, Imperative Shell | `18.2` |
| Referential Transparency Replacement | `18.2` |
| Concept Inventory (Decomposition Heuristic) | `17.2` |

### Decomposition Smells

[references/decomposition/smells.md](../references/decomposition/smells.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| D1: High Cyclomatic Complexity | `17.1` |
| D2: Unfocused Method | `17.2` |
| D3: Too Many Variables | `17.2` |
| D4: Feature Envy | `17.3` |
| D5: Lost in Translation | `15.2` |
| D6: Nested Composition Hiding Side Effects | `18.1` |
| D7: Low Cohesion Section Inside a Class | `17.4` |
| D8: System-Wide Sprawl | `33.1` |
| D9: Orphaned Generated Code | `33.5` |

### Stratified Design

[references/decomposition/stratified-design.md](../references/decomposition/stratified-design.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Compare policy and representation changes | `19.1`, `19.2`, `19.3` |

### Outside-In TDD Patterns

[references/outside-in-tdd/patterns.md](../references/outside-in-tdd/patterns.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Walking Skeleton | `12.1` |
| Characterisation Test | `18.4`, `48.1` |
| Devil's Advocate | `13.1` |
| Transformation Priority Premise (TPP) | `13.3` |
| Fake Object for I/O Isolation | `12.4`, `51.3` |

### Separation of Concerns Patterns

[references/separation-of-concerns/patterns.md](../references/separation-of-concerns/patterns.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Decorator | `22.1` |
| Read-Through Cache Decorator | `23.3` |
| What to Log | `22.2` |

### Evolution Patterns

[references/evolution/patterns.md](../references/evolution/patterns.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Feature Flag (Calendar Flag Variant) | `26.1`, `26.2` |
| Method-Level Strangler | `27.1` |
| Class-Level Strangler | `27.2` |
| Expand-Contract (Database and Schema Migration) | `47.1`, `47.2`, `47.3`, `47.4` |

### Troubleshooting Patterns

[references/troubleshooting/patterns.md](../references/troubleshooting/patterns.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Reproduce-as-Test | `30.2` |
| Git Bisection | `31.2` |
| Isolate-Then-Fix (Non-determinism) | `31.1` |

### Measurement Commands

[references/tooling/commands.md](../references/tooling/commands.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Cyclomatic Complexity (rule: review above 15) | `17.1` |
| Dependency Cycles and Layer Violations (smell D8) | `33.1` |
| Duplication | `33.4` |
| Dead and Orphaned Code (smell D9) | `33.5` |
| Hotspots and Change Coupling (behavioural analysis) | `33.3` |
| Test-Oracle Strength (automated Devil's Advocate) | `13.1` |
| Architecture Tests (make stable constraints executable) | `44.1` |

### Practices Glossary

[references/practices-glossary/knowledge.md](../references/practices-glossary/knowledge.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Arrange Act Assert | `6.1`, `6.2`, `6.3`, `51.1` |
| Bisection | `31.2` |
| Checklist for a New Code Base | `10.1`, `10.2` |
| Command Query Separation | `20.1` |
| Count the Variables | `17.2` |
| Cyclomatic Complexity | `17.1` |
| Explicit Seams for Cross-Cutting Concerns | `22.1` |
| Devil's Advocate | `13.1` |
| Feature Flag | `26.1` |
| Functional Core, Imperative Shell | `18.2` |
| Complementary Communication | `21.3` |
| Justify Exceptions from the Rule | `44.2` |
| Parse, Don't Validate | `15.2` |
| Explicit Boundary Parsing | `15.3` |
| Red Green Refactor | `13.2` |
| Regularly Update Dependencies | `28.3` |
| Reproduce Defects as Tests | `30.2` |
| Review Code | `25.2` |
| Semantic Versioning | `28.1` |
| Separate Refactoring of Test and Production Code | `14.2` |
| Slice | `12.1` |
| Strangler | `27.1` |
| Stratified Design | `19.1` |
| Threat-Model | `37.4`, `61.1` |
| Transformation Priority Premise | `13.3` |
| X-driven Development | `12.3`, `14.3` |
| X Out Names | `21.2` |

### PR / Code Review Checklist

[references/teamwork-git/checklist.md](../references/teamwork-git/checklist.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Decision, risk, evidence and ownership | `25.3`, `63.3`, `63.4` |

### STRIDE Threat-Model Checklist

[references/security/checklist.md](../references/security/checklist.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Outcome and risk owners | `37.4`, `61.4` |

## Workflows and project heuristics

### Guidelines for selecting material

[guidelines.md](../guidelines.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Examples by Stack and reference selection | `49.1`, `49.2`, `49.3` |

### Add a Feature Outside-In Workflow

[workflows/add-feature-outside-in.md](../workflows/add-feature-outside-in.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| add-feature-outside-in | `12.1`, `49.3` |

### Refactor Code Workflow

[workflows/refactor-code.md](../workflows/refactor-code.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| refactor-code | `18.3`, `48.1`, `48.2`, `48.3` |
| Proposed design and implementation evidence | `48.1`, `48.2` |

### Code Review Workflow

[workflows/review-code.md](../workflows/review-code.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| review-code | `25.2` |

### Focused diagnosis

[workflows/diagnose-code.md](../workflows/diagnose-code.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| diagnose-code | `1.4`, `1.5`, `2.5`, `3.5`, `59.1` |
| Design defect, material gap and implementation freedom | `59.1`, `59.2`, `59.3` |

### Debug a Defect Workflow

[workflows/debug-defect.md](../workflows/debug-defect.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| debug-defect | `30.4` |

### Threat Model Workflow (STRIDE)

[workflows/threat-model.md](../workflows/threat-model.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| threat-model | `37.4`, `61.4` |
| Describe the component and record the six STRIDE decisions | `61.1`, `61.2`, `61.3` |

### Operationalize a Finding Workflow

[workflows/operationalize-finding.md](../workflows/operationalize-finding.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| operationalize-finding | `4.1`, `4.2`, `4.3`, `4.4`, `44.1`, `44.3`, `44.4` |

### Maintain project heuristics

[workflows/maintain-project-heuristics.md](../workflows/maintain-project-heuristics.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Assess a review comment | `45.1`, `45.2`, `45.3` |
| Record agreed wording | `45.4`, `46.1` |
| Compare project and shared heuristics | `45.3`, `46.4`, `62.1`, `62.2` |
| Local exception, covered entry and candidate for shared guidance | `62.1`, `62.2`, `62.3` |

### Project heuristic files

[references/project-heuristics.md](../references/project-heuristics.md)

| Source rule or practice | Case and expectation |
| --- | --- |
| Entry, grouping and edits | `45.4`, `46.1`, `46.2`, `46.3`, `62.4` |
| Broken links and approved retirement of the last group entry | `62.4` |
