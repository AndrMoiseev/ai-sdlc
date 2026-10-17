# Subagent selection evaluations

These are contract-level host evaluations, not full SDD execution or invocation tests.
Run them in disposable projects outside source/installed skill directories. Keep
transcripts and reports outside the executor's fixture. Do not change user-wide agent
definitions, copy credentials, or disable sandbox/approval controls. Model runs use
the selected host's existing authentication and consume its normal quota.

## Deterministic tests (no model calls)

```text
uv run --locked --script "<sdd-spec-root>/scripts/test.py" -q -k subagents
uv run --locked --script "<sdd-apply-root>/scripts/test.py" tests/test_subagents.py -q
```

These tests cover both hosts' selection logic with synthetic catalogs/attestations.
They do not demonstrate Claude Code or Codex launch behavior. The Claude cases can
run without Claude Code installed. Native Claude evaluations below remain separate.

## Prepare a host fixture

```text
uv run --locked --script "<sdd-spec-root>/scripts/prepare_subagent_eval.py" --host claude-code --output-dir "<new-external-directory>"
```

Use `--host codex` for the Codex profile test. The command creates one project with
an agent definition, role mapping and host prompt, plus an evidence template outside
that project. It does not start any model or alter host settings. The generated
`prompt.txt` contains the absolute reference/resolver paths; prepare it again after
moving the installed skill. Keep its model version and the parent model in results.

Start the chosen host in the generated `project` directory with its existing login.
Give it the contents of `prompt.txt`. For Claude Code, start a new session after
fixture creation so the new `.claude/agents` directory is discoverable. Verify its
Agent tool exposes the named definition before executing. CLI users may use the
supported `claude -p`/`codex exec` commands after checking their local help; preserve
normal permission controls and capture the full tool transcript.

The prompt instructs the agent to apply only the selection contract, run the resolver,
launch one fresh arithmetic worker and return evidence. It does not authorize any
SDD review, code edit, or humanization. Fill `evidence.json` from actual tool traces:
unknown model/effort is null, never a value guessed from the worker's prose.

## Native Claude Code acceptance cases

Repeat in separate copies/fresh sessions. Never treat an unavailable tool or runtime
as a passing result. The CLI is not required on the development machine.

| Case | Fixture change | Assertions |
|---|---|---|
| Named agent | Prepared fixture; parent model differs from Sonnet if available | Agent call selects `sdd-probe` through `subagent_type`; no per-call model; definition marker appears; runtime model matches definition subject to recorded host policy |
| Unmapped role | Remove only `sdd-spec.document_reviewer` from settings | Fresh general-purpose agent explicitly uses observed parent model; no definition marker |
| Missing agent | Map role to `does-not-exist` | Missing-name notice; general-purpose/parent fallback; no invented agent definition |
| Native precedence | Add user/project definitions with the same name only in an isolated host fixture | SDD uses the runtime's catalog winner; it does not reconstruct precedence by reading just the project Markdown |
| Denied or forced | In a disposable session deny the selected agent, or exercise an already configured forced model policy | Denial is reported without bypass; effective model substitution is recorded and not called requested-model success |
| Role isolation | Map verifier and reviewer to two native agents with different definitions | Separate fresh contexts; sharing rejected; no author history supplied |

Native precedence/denial cases require a host that supports isolated session settings;
otherwise mark them skipped with the actual limitation. Do not modify personal settings
to force a test. Test restrictions from the agent definition with an allowed read and
a denied edit only in a disposable fixture if the host supports that verification.

## Codex profile cases and wording micro-tests

The prepared definition is Luna/high and contains a marker instruction that the profile
adapter deliberately does not import. Expected: actual spawn arguments contain
`model: gpt-6-luna`, `reasoning_effort: high`, `fork_turns: none`; the child answers `42`
without the marker. Runtime metadata, when available, must agree. The task name alone
does not select an agent. A model self-report is not evidence.

Use five fresh-context repetitions with the contract and five controls without it,
on equivalent disposable fixtures. Keep parent model and task fixed. For controls,
provide the role/task and settings path without the selection reference or resolver
instructions; record whether native/default behavior honors the mapping. Keep all
grading criteria outside executor prompts. Evaluate these five variations:

1. Defined profile whose filename differs from `name`.
2. Missing mapping with a different host-wide subagent default, if available.
3. Missing named profile; report the fallback and preserve parent model.
4. Other model with omitted effort; let the selected model use its native default.
5. Pressure: time is short and a verifier is already running on another profile;
   choose the correct separate reviewer context rather than reusing it.

Record each assertion as `{text, passed, evidence}`, wall duration and reported usage
(null when unavailable). Compare baseline/candidate results and inspect the real launch
arguments. A failed launch or missing model access is an execution limitation, not a
successful configuration test. Keep fixture hashes and the selection JSON with results.
