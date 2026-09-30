# SDD CREATE behavior evaluation

This is synthetic instruction evaluation, not a real-project SDD pilot or automatic invocation test. The candidate is explicit-only, so discovery was skipped.

`runs.json` maps the 14 runs: five independent stale-review pressure repetitions per variant, plus one paired plan-ownership and one paired cancellation-resume scenario. `prompt.txt` is the exact executor input. `stdout.jsonl` contains the CLI tool trace and commentary; `response.md` is the final answer. `run.json` and `timing.json` contain CLI-reported execution status, elapsed time, and usage. Each CLI process uses its configured default model without an override.

Three earlier fresh native samples are preserved in `native-exploratory/` and excluded from the benchmark. Native thread exhaustion blocked further spawning, so the entire 14-run set was restarted with the matching Codex CLI. The first read-only CLI probe failed under the outer filesystem sandbox; the approved retry allowed CLI initialization while every evaluation child retained `--sandbox read-only`. The CLI probe is not a behavior result.

Fixtures are separate directories outside repository ancestry, under the temporary root recorded in `temp-root.txt`. Baselines receive no candidate path. Skill catalogs remain inherited from the host; executors report whether `sdd` is listed. This is read-scope isolation, not an ACL guarantee that the candidate is unreadable to a baseline. Check the actual trace for candidate or original-repository reads before interpreting baseline results. No global skill installation was changed.

Guard scenarios supply the decision facts in the prompt and use empty disposable fixtures. They test an action response, not actual hash/review reconstruction on disk. The plan scenario supplies valid proposal/spec/design, a current synthetic independent report, and explicitly labeled synthetic user approvals with byte-hash manifests. The fixture is validated before execution; setup failures are not scored as skill failures.

Preparation scripts are retained: `prepare.py`, `prepare_fixtures.py`, `run_cli_batch.py`, and `prepare_viewer.py`. They use the temporary root from `temp-root.txt`; initialize a new directory with PowerShell `New-Item` before a new run. `prepare.py` freezes the candidate and writes prompts; `prepare_fixtures.py` requires PyYAML and markdown-it-py from the locked skill environment. `run_cli_batch.py` invokes the conductor harness with fresh CLI processes, paired variants, and normal read-only child permissions. It preserves any prior generated run artifacts under `native-exploratory` before replacement; use a new iteration directory for a new experiment.

The candidate was not revised in response to these outputs. User review of the static viewer precedes any future wording changes.
