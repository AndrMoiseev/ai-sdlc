# Runtime setup (pre-flight)

Read before running scripts or evaluations. Resolve `<skill-root>` from the loaded SKILL.md. Use absolute script, fixture and output paths when working outside their directories. The consuming project needs no Python manifest, lockfile or environment.

## Choose the execution path

If the current agent is neither Codex nor Claude Code, or the host is unknown, start with the [arbitrary agent path](generic.md). The CLI choices below describe the bundled runner, not an exhaustive list of agents that can follow this skill.

1. Prefer the current harness's native subagents for behavior runs, grading, and analysis when they support fresh context and the required workspace isolation. Native Codex and Claude Code agents use their host session; a missing CLI or API key does not block this path.
2. Use the CLI adapter when native subagents are unavailable or cannot provide a clean run. `run_task.py` runs behavior prompts; `run_eval.py` measures discovery; `improve_description.py` and `run_loop.py` optimize descriptions. All accept `--harness auto|codex|claude-code`.
3. If neither path works, report the specific unavailable capability. Continue local structural checks and provide runnable manual scenarios; do not substitute the author's current conversation for an independent baseline.

For CLI selection, `scripts/harness.py` applies this precedence:

| Priority | Signal |
| --- | --- |
| 1 | Explicit `--harness codex` or `--harness claude-code` |
| 2 | `SKILL_CONDUCTOR_HARNESS` |
| 3 | Current harness: `CODEX_THREAD_ID` for Codex; `CLAUDECODE` or `CLAUDE_CODE_ENTRYPOINT` for Claude Code |
| 4 | The sole installed CLI (`codex` or `claude`) |

`auto` delegates to the next signal. Conflicting current-harness signals, two installed CLIs without a selection, or no installed CLI produce an actionable error. An unavailable selected CLI is an error; it does not silently switch providers. State the selected harness before a run. Keep paired baseline and with-skill runs on the same harness and model.

## Check prerequisites

Verify `uv --version`, `uv cache dir`, the required script and its adjacent
`<script>.lock`. Each entry point declares Python 3.10+ and its dependencies in
PEP 723 metadata. uv creates its environment in the user cache, independently of
the consuming project. Run the required script directly, including installed
copies at their actual paths:

```text
uv run --locked --script "<skill-root>/scripts/eval_skill.py" "<skill-path>"
```

uv downloads missing dependencies and a suitable Python when needed, then executes
the script. The same command rebuilds its environment after a move or cache cleanup;
no separate sync is required. Pass the script directly to uv so its metadata and
lockfile are applied. Entry points disable bytecode before importing local modules.
If network or filesystem permissions block installation, report the actual error
and use the host's normal permission mechanism. Change a stale lockfile only as an
explicit dependency update, using `uv lock --script`.

Add `--offline` only for explicitly requested offline work or offline regression
tests with locally available dependencies. It limits uv's network access, not the
script or a spawned model CLI. A missing package in that mode is an expected error.

Cache placement is a once-per-user uv setting. On Windows, set `UV_CACHE_DIR`
to an absolute `uv-runtime/cache` directory under the system temporary directory.
Set `UV_TOOL_DIR` to its `uv-runtime/tools` sibling for third-party `uvx` calls,
which also need a writable tools lock. Restart the agent application after setting
user variables and confirm the inherited paths. These disposable directories may
be cleared by the system; keep retained reports elsewhere. uv also needs access to
its Python installation directory when downloading an interpreter. Project files need no changes
when the host already permits writing to its temporary directory; if it does not,
report that restriction rather than claiming the setup succeeded.

For a CLI path, verify the selected CLI's version and existing login, then run a small read-only prompt before starting the batch. Codex uses `codex exec --json`; Claude Code uses `claude -p --output-format stream-json`. Authentication follows that CLI's existing configuration. Do not require an Anthropic API key for Codex or native subagents, copy credentials into fixtures, print secrets, or add flags that bypass permissions. If login is missing, report the selected CLI's authentication requirement.

Omit `--model` to use the selected CLI's configured default. If a model is specified, use a model supported by that harness and record it. Do not carry a Claude model identifier into a Codex run, or vice versa.

## Prepare independent runs

- Give each run a separate copy of the same fixture state, outside any ancestor directory that exposes the candidate skill. New conversations alone do not isolate files or inherited skill catalogs.
- For native agents, start with fresh context (for example, `fork_turns="none"` in Codex), pass only the task, fixture location, and assigned skill instructions. Verify which skills and repository instructions the agent can still see. If the baseline inherits the candidate, use a clean CLI session or report the isolation limit.
- For CLI runs, inspect project, ancestor, and user-level skill discovery. For discovery tests, install only the candidate in the target harness's project skill directory (`.agents/skills` for Codex, `.claude/skills` for Claude Code); give the baseline no copy. Account for any user-installed copy before calling the baseline clean. Do not alter a user's global installation to hide it.
- Keep answers, assertions, prior outputs, and grader instructions out of executor context. Explicit behavior runs can point the with-skill agent to the candidate's `SKILL.md`; that tests instruction following, not automatic discovery.
- Give write access only when the task needs fixture edits, and only within the disposable run workspace. A workspace argument is not proof of isolation: inspect discovered instructions and execution traces, and retain normal sandbox and permission enforcement.

## Check fixture dependencies before model execution

Read the tested skill's runtime instructions and the flows exercised by the scenario.
Inventory their required skills and resources, including transitive dependencies.
Copy complete dependency packages into each isolated fixture and use the paths the
executor will see. A dependency installed in the author's repository does not satisfy
this check. Keep dependency versions identical between baseline and candidate;
only the skill under test differs. A no-skill control can declare an empty inventory.

Save a JSON fixture manifest outside the executor's context. List required files
relative to the fixture root. For example, an sdd-spec scenario that edits Russian
documents needs its humanizer dependency even when it does not generate diagrams:

```json
{
  "schema_version": 1,
  "required_files": [
    ".agents/skills/sdd-spec/SKILL.md",
    ".agents/skills/humanizer-ru/SKILL.md",
    ".agents/skills/humanizer-ru/references/patterns.md",
    ".agents/skills/humanizer-ru/scripts/lint.py"
  ],
  "expected_missing_files": []
}
```

Use the host's actual discovery paths (for example `.claude/skills` for Claude Code).
For a scenario deliberately testing a missing dependency, put its entry point in
`expected_missing_files` instead of `required_files`. The runner verifies absence
as well as presence. The inventory is explicit: the checker cannot infer dependencies
described only in prose, so reconcile it with runtime instructions before the batch.

Run the command below with `--preflight-only` and a separate output directory before
the first model call. It checks readable resources inside the fixture, rejects paths
escaping it, and writes `preflight.json` without starting a model. The same check runs
again before every real execution. A missing dependency is a fixture setup error:
repair the fixture before the batch, rather than scoring it as a skill failure or
making the model search the author's environment. Filesystem checks do not prove
runtime tools, authentication, or model-visible discovery; verify those separately
with the small read-only probe above before scaling up.

## Run a behavior scenario

Prepare `prompt.txt` and a disposable fixture workspace. In the with-skill prompt, explicitly invoke or reference the skill using the selected harness's supported mechanism. Use the same task without the skill instruction for the baseline.

```bash
uv run --locked --script <skill-root>/scripts/run_task.py --harness auto --prompt-file prompt.txt --workspace <fixture-copy> --fixture-manifest fixture.json --output-dir <run-artifacts>
```

Add `--allow-writes` for scenarios that edit fixture files. `--model` and `--timeout` are optional. Keep output artifacts outside the fixture when the task must not read its own trace. The runner saves the response, execution trace, run metadata, and timing; inspect completion/error status before grading. A timeout, permission failure, or authentication error is a failed execution, not a negative skill-discovery result.

The CLI runner requires `--fixture-manifest` and writes `preflight.json` before model execution. Completed executions also write `response.md`, `stdout.jsonl`, `stderr.txt`, `run.json`, and `timing.json`. Use a new output directory per run. `run.json` records the selected harness and requested model; a `null` model means the CLI default was used, not that the parent conversation's model was inherited.

For native runs, save equivalent artifacts yourself. Record measured wall time and only token counts reported by the harness. Use `null` for unavailable timing or usage fields; never infer tokens from text length or treat missing metrics as zero.

## Invocation policy

For explicit-only skills, preserve the target harness policy (Codex: `policy.allow_implicit_invocation: false` in `agents/openai.yaml`; Claude Code: `disable-model-invocation: true` in frontmatter). Skip discovery evaluation and description optimization. Keep explicit behavior scenarios, independent baselines, and repeat-update checks. Report the skipped stages separately from successful checks.

## Sources

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex skills and invocation policy](https://developers.openai.com/codex/skills)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference); verify supported options with the installed CLI.
