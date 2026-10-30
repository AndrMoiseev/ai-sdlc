# Explorer handoff: prepared evaluation

This procedure is prepared, not run. Execute actual behavioral, trigger, control
or repeated agent evaluations only after a separate explicit user instruction
for this evaluation. Plan approval and deterministic fixture validation do not
authorize them. Without that instruction report **not run; agent behavior not
confirmed**. The owning criterion is AC-explorer-workflow; other Explorer criteria
retain their original task owners.

## Inputs and expected observations

[explorer-fixtures.json](explorer-fixtures.json) supplies three scenario prompts,
source files, an exact check template, the synthetic AC and grader expectations.
Matching entries 16–18 in [evals.json](evals.json) make the scenarios discoverable.
The sample JUnit reports are synthetic preparation data, never execution evidence.

| Case | Expected observation |
|---|---|
| ordinary-success | Explorer runs the registered set; the orchestrator passes its machine summary and evidence references to a separate verifier. The verifier inspects AC and sources, concludes passed, and does not rerun commands or automatically load the full log. |
| verbose-failure | The nonzero exit blocks progress. The compact excerpt remains bounded, and the full raw artifact retains both markers and every diagnostic line. The verifier reads the necessary referenced failure detail. No repair/retry happens without its reservation. |
| mandatory-skip | Exit zero and a passing smoke test coexist with one required skipped test. The verifier maps that skip to AC-order-ids, records unavailable and blocks review/acceptance pending sufficient coverage. |

## Freeze and isolate

1. Preserve complete candidate and pre-Explorer old-skill bundle bytes with commit
   IDs and file-hash inventories outside the project, skill collections and uv cache.
   Use the same host/model and unchanged third-party dependencies for paired runs.
   This change alters the shared/apply contract together, so the control uses its
   matching old SDD dependencies. Record those version differences; the comparison
   tests the bundle change and cannot attribute an effect to one sentence or skill.
   A snapshot taken after the Explorer implementation is not the old control.
2. Inventory dependencies of the exercised flows: sdd-apply and its matching
   sdd-shared are required. The synthetic approved plan is prepared before the
   run, so these cases do not invoke sdd-spec, sdd-sync or setup. Keep required role
   definitions and permission controls with each arm. Use conductor runtime setup
   for interpreter, external uv directories and actual host capabilities.
3. Make separate external fixture workspaces for every case, variant and repetition.
   Preserve complete source snapshots externally, then copy runtime instructions
   and resources into the worker-visible collection without development tests/evals
   or grading files. Inspect instructions and references for required resources
   before omitting anything; keep an inventory of the runtime copy. Graders retain
   this procedure, expected values and sample reports outside worker access.
4. Confirm that control workers cannot discover the candidate through filesystem
   ancestors, user-installed skills, shared catalogs or prior conversation. Fresh
   context alone does not prove isolation. Keep normal permissions; report a blocked
   comparison if the host cannot isolate it. Do not modify global installations.

## Materialize the scenario

After authorization, materialize common sources plus the case's overrides in its
fixture. Add a valid ordinary change for order-export with one task covering the
supplied AC, and only the registered deterministic check. Prepare approvals as
clearly synthetic fixture inputs, never as approvals for a real project. Use the
existing document templates and each arm's normal API to prepare its own execution;
execution state is not portable between old and candidate bundles.

Bring each arm to a frozen local candidate awaiting independent checks. Use a
passing initial source/test set to obtain a real baseline first, then introduce
the case variant through the executor and candidate operation. Preserve baseline
and preparation traces separately from the measured independent-stage decision.
Do not fabricate accepted events, launch identities or baseline passes. If the
old bundle cannot reach that point, retain the limitation as a control result.

Resolve `{python}` to an external interpreter with pytest and `{artifacts}` to a
unique permitted output directory. Substitute placeholders and register the exact
argument array/configuration before running it; use the same test semantics in
both arms. Disable bytecode and keep pytest temporary files/JUnit output external.
The tests and command are fixture inputs; the sample reports and expected decisions
are not. Save the actual registry, candidate SHA and normative basis per arm.

## Execute only the separately authorized scope

Dispatch fresh native contexts or a proven clean CLI session under conductor
runtime setup. Give workers only the selected prompt, sources, packet and assigned
runtime instructions. Never give them expected decisions, sample reports, previous
answers or this grading procedure. Record actual roles and tool calls; the old arm
uses its own workflow, even if it has no Explorer role. Keep the paired prompts,
source bytes, model and conditions equal except for the named version differences.

For the candidate, observe the Explorer launch, registered independent check run,
and orchestrator handoff of check-run identity, scope/stage, basis, registry revision,
check IDs, summary and primary evidence references. Keep the verifier independent
of the author and Explorer. Read raw objects through the supported API when needed;
reading evidence must not produce a hidden second command execution. Record the
separate criterion conclusion. Stop at the requested decision, before actual repair,
integration or acceptance; the fixture asks for review eligibility, not delivery.

Measure the whole selected skill evaluation set, including fixture preparation,
launches, waits, grading and retries. Apply the current project limit and any explicit
user override to that whole set; new roles do not reset it. Stop the set and its
process tree if the limit is reached. Do not launch an unauthorized subset merely
because other scenarios are prepared. Five fresh repetitions per wording/arm and
a no-guidance control are conductor's pressure-test targets; include them only in
an explicit authorized scope whose time allowance permits them. Report any omitted
control or repetition and the resulting limit on conclusions.

## Grade observed evidence and retain it

For every case and arm retain the prompt, package inventories, actual launch and
tool transcript, registry/basis, complete stdout/stderr, actual structured reports,
SHA-256 references, check summaries, criterion conclusion and source diff. Keep
all artifacts outside the fixture's worker-visible inputs and skill packages.
Check raw artifact hashes before/after handoff and compare them with the original
captured bytes. For the verbose case inspect both markers and all diagnostic lines,
including text outside the compact excerpt. Preserve failures and missing artifacts.

Grade each expectation from actual actions and primary evidence with conductor's
`text`, `passed`, `evidence` fields. Text matching an instruction, a synthetic report,
a fixture test pass, or an agent's claim does not establish behavior. Record who
executed each command, which raw objects the verifier read, any rerun and its reason,
and whether a mandatory skip blocked progress. Unavailable or contaminated runs
stay explicitly unconfirmed. Save actual wall time and available token/cost metrics;
unknown metrics are null. Compare candidate and old-skill outcomes, disclose shared
version differences, and present the evidence-backed result before any further edits.

## Related prepared procedures

The spec [manual procedure](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-spec/evals/manual.md)
uses its existing `evals/fixtures/explorer.json` for pre-change research, document
checks and lost artifacts. The sync [manual procedure](https://github.com/AndrMoiseev/ai-sdlc/blob/main/skills/sdd-sync/evals/manual.md)
uses `evals/explorer-read-fixtures.json` for separate execution/conclusion states.
Their inputs and AC owners stay in those packages; measure each authorized skill
set separately. Links here describe related evaluation scope and do not make
sdd-spec or sdd-sync runtime dependencies of an apply/shared installation.
