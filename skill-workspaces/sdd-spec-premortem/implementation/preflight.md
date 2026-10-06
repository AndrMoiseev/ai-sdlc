# Behavioral evaluation preflight

Date: 2026-10-06. Scope: execution setup only; no skill changes or scored evaluations.

## Result

The initial sandboxed CLI probe failed before model execution with Windows access denied. The root agent subsequently repeated the same read-only probe using normal permission escalation; it completed successfully. The executor reported the TEMP working directory, no sdd-* catalog entries, and no repository AGENTS.md. Independent explicit behavior runs are therefore using this CLI path and disposable fixtures. Native fresh context still receives repository instructions and the host skill catalog and was not used as a behavioral baseline.

## Native context evidence

This agent received the repository AGENTS.md instruction to use sdd-skill-conductor, the working directory C:/Users/Andrew/repos/ai-sdlc, and the full host catalog. The catalog includes repository entries for archify, humanizer-ru, and sdd-skill-conductor. It does not list sdd-spec, but the shared filesystem exposes `.agents/skills/sdd-spec` and the repository skill sources. Fresh conversation therefore does not establish fixture isolation. No candidate skill body or behavioral assertions were read by this preflight agent.

## Runtime evidence

- `codex --version`: codex-cli 0.160.1.
- `codex login status`: Logged in using ChatGPT. No credentials read or copied.
- `uv --version`: uv 0.12.5.
- `scripts/run_task.py` and `eval-viewer/generate_review.py` exist under skills/sdd-skill-conductor.
- Neither user skills root (`~/.agents/skills`, `~/.codex/skills`) contains a path matching sdd-spec.
- No AGENTS.md exists at C:/, C:/Users, the user home, AppData, AppData/Local, or AppData/Local/Temp. No ~/.codex/AGENTS.md exists.
- A disposable empty directory was created: C:/Users/Andrew/AppData/Local/Temp/sdd-premortem-preflight-d02bdf106d62457295b341ff4eed3358.

CLI probe (normal read-only sandbox, default configured model, no permission bypass):

```powershell
codex exec --json --ephemeral --skip-git-repo-check --sandbox read-only --color never -C C:/Users/Andrew/AppData/Local/Temp/sdd-premortem-preflight-d02bdf106d62457295b341ff4eed3358 'Read-only preflight. Do not use tools or read files. Return your working directory, the names of skill catalog entries starting with sdd-, and whether any repository AGENTS.md instructions were supplied. Do not perform any other task.'
```

Exit 1. CLI warns that it cannot clean/create ~/.codex/tmp/arg0 paths, then reports:

```text
Error: failed to initialize in-process app-server client: Отказано в доступе. (os error 5)
```

The initial probe produced no behavioral output, model usage, or independent catalog confirmation. The successful root retry reported 16,861 input tokens and 69 output tokens; these are probe metrics, not evaluation scores. No global installations or settings were changed. The root retry retained the ordinary read-only sandbox and did not use permission-bypass flags.

## Concrete isolated execution procedure

After resolving CLI initialization permission through the normal approval mechanism, repeat the read-only probe and inspect the returned catalog. Do not count runs until that succeeds.

1. Create a new UUID-named directory under the OS temp directory, outside the repository ancestry.
2. Create separate baseline and candidate fixture copies under that directory, containing identical scenario files. Store outputs, prompts, assertions, and grader instructions outside executor fixture directories.
3. Give baseline no candidate or repository paths. For explicit behavior testing, copy the complete candidate package into candidate/.agents/skills/sdd-spec and explicitly invoke it in the candidate prompt. This tests explicit behavior, not discovery.
4. Run each through the existing adapter, using the same selected harness and configured model:

```powershell
uv run C:/Users/Andrew/repos/ai-sdlc/skills/sdd-skill-conductor/scripts/run_task.py --harness codex --prompt-file <outside-fixture-prompt.txt> --workspace <temp-fixture> --output-dir <outside-fixture-output> --allow-writes
```

5. Inspect run.json status and stdout.jsonl to confirm successful completion and absence of repository/candidate reads by baseline. The adapter retains the normal workspace-write sandbox. Do not use permission-bypass flags.
6. Run at least five fresh repetitions per wording variant plus no-guidance control, and required pressure scenarios. Preserve response.md, stdout.jsonl, stderr.txt, run.json, timing.json. Record unavailable native token metrics as null.

If the CLI remains unavailable, report behavioral checks as blocked; structural checks can proceed with uv. Do not substitute the author conversation for independent baselines.

## Follow-up: approved CLI isolation probe

The root agent retried the identical read-only probe using the normal require_escalated approval mechanism and reported success (session35371). The executor reported no sdd-* catalog and no repository AGENTS instructions. No global configuration change or sandbox bypass was used. Subsequent behavioral execution uses the standard run_task.py adapter with workspace-write sandbox in per-run TEMP fixtures; the escalation permits CLI initialization and existing uv cache access.

Reusable setup is fixtures.py + run_behavior.py. Fixture authority and initial invalidated cases are documented in fixture-authority.md. Frozen split.json and coverage.json were retained. Baseline and candidate use separate full package copies; the executor never receives evaluator assertions. Execution limitations are stored in run.json rather than counted as behavioral failures.
