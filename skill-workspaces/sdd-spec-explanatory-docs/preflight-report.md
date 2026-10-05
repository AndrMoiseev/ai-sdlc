Current status: user selected LOCAL CHECKS ONLY. Behavioral LLM runs are skipped per user; no approval is pending. Relative evidence paths below refer to C:/Users/Andrew/AppData/Local/Temp/sdd-spec-explanatory-evals-caafff7c123f4f4b8dbd3e7402072026/. See local-evidence.md for current checks.

# Independent evaluation preflight

- Old package frozen before edits: old_skill/ and old-manifest.json (SHA256, all files recursively including hidden).
- Native clean context unavailable: native catalog includes repository candidate; no native baseline claimed.
- uv 0.12.5; Codex CLI 0.160.0; existing login verified using `codex login status` (ChatGPT). No credentials copied or printed.
- Global C:/Users/Andrew/.agents/skills and .codex/skills have no sdd-spec. Temp ancestor AGENTS.md checks found none.
- Default uv cache access denied; selected external `uv-cache` directory beside report. PYTHONDONTWRITEBYTECODE=1 used for runner.
- Initial CLI smoke: app-server access denied under outer sandbox. Evidence smoke/.
- Escalated outer runner, inner `codex exec --json --ephemeral --skip-git-repo-check --color never --sandbox read-only -`: completed. Response confirms no sdd-spec catalog or AGENTS.md exposed in fresh fixture. Evidence smoke-escalated/ includes transcript, run.json and timing.json. Duration 36.609 s; input_tokens 33920, output_tokens 143, total 34063. Requested model omitted, configured CLI default retained.
- `node .agents/skills/archify/bin/archify.mjs doctor`: successful.
- Actual bundled workflow example copied into archify-probe/candidate.json. Outer sandbox finalize fails spawn EPERM (not missing browser). Escalated finalize succeeds validate/deliver/check/browser-check. Installed Archify 3.0.1 current. Real local Chrome executed. All receipts are in archify-probe/. No screenshot or perceptual inspection claimed. Example is an environment probe, not evidence of new sdd-spec behavior.

## Behavioral execution blocker

Automatic approval review rejected the first old-skill behavior baseline BEFORE execution. The rejected command would create a synthetic order-retry fixture, copy frozen old_skill into assigned-skill, and run conductor run_task.py --harness codex --allow-writes --timeout 300, keeping the inner workspace-write sandbox. No fixture from that command was created.

Stated reason: external Codex CLI with workspace-write over copied private skill and fixture could export sensitive repository contents to an untrusted service; user authorized evaluation but not this specific payload disclosure. The rejection explicitly prohibits workaround or indirect execution. No behavior batch, no micro repetitions, and no baseline grading have been executed following that rejection. Need explicit user approval or additional evidence establishing authorization/low risk before retry. Read-only smoke success does not override this payload rejection.

Git origin is git@github.com:AndrMoiseev/ai-sdlc.git, which by itself does not establish public visibility. `gh` is unavailable, so visibility was not established. No remote payload was sent in investigating this blocker.

## Reproduction after authorization

Use the runner at C:/Users/Andrew/repos/ai-sdlc/skills/sdd-skill-conductor/scripts/run_task.py through uv; use a separate external fixture and output directory for each version/scenario; assign only old_skill for baseline and frozen candidate for new runs; pass identical tasks. Keep eval answers/gradings outside executor fixture. Retain run.json, timing.json, stdout.jsonl, response.md, stderr.txt. Do not label execution failures as failed behavioral assertions. Paired scenarios and micro repetitions remain pending.
