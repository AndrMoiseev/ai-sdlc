# Shared uv environment validation

Date: 2026-10-07. Host: Windows, Python 3.14.7, uv 0.12.5, APM 0.32.0.
This implementation supersedes the earlier per-copy prepared-runtime approach.

Follow-up: made uv invocation an explicit entry rule in conductor's SKILL.md,
covering its own Python scripts and commands authored for other skills. The
package-runtime reference also states that Python child processes inherit the
uv-selected interpreter. Structural evaluation passed all 17 deterministic
criteria. Both managed copies and their deployment hashes were updated and
verified; all three conductor packages remain free of generated runtime state.

## Implemented contract

- One root pyproject.toml, uv.lock, .venv and .cache/uv for the repository.
  The root references sdd-spec as a virtual local dependency, so its dependency
  declarations stay in the portable skill without being duplicated at the root.
- Preparation: uv sync --locked. Execution: uv run --project . --locked --offline
  python -B from the root; uv run --directory <repo> from another directory.
- Removed per-copy launchers, readiness markers and skill-local uv.lock files.
  Updated source and managed copies, conductor runtime guidance and APM hashes.
- Preserved existing user-cache environments; the new commands do not select them.

## Checks performed

- Root uv lock and uv sync --locked completed with network access. Packages were
  installed only in the root .venv; uv cache is under root .cache/uv.
- Source sdd-spec suite: 135 passed, 1 skipped.
- Installed Codex sdd-spec suite from this external working directory, through
  the same root uv project: 135 passed, 1 skipped. Pytest cache was explicitly
  directed to root .cache/pytest.
- Conductor smoke tests: 12/12 passed. Child checks inherit the interpreter of
  the outer uv invocation and disable bytecode writes. Their output uses UTF-8.
- verify.py exercised the real root environment in the sandbox with offline uv:
  source, Codex and Claude copy paths all selected root .venv. check and snapshot
  succeeded against an isolated template fixture for every copy. No specification
  from the user's active change was used as a fixture.
- Separate unprepared project fixture failed with missing local dependencies;
  changed dependency declarations also failed offline. Neither rewrote uv.lock.
  Detailed command outputs are in results.json.
- Standalone consumer fixture: uv add --no-workspace ./.agents/skills/sdd-spec,
  uv sync --locked and offline check succeeded with the consumer's own common
  environment. Initial uv init implicitly registered the nested fixture in the
  parent workspace; that registration was removed. Documentation now specifies
  uv init --bare --no-workspace for creating an independent consumer project.
- Fresh-context reviewer /root/review_shared_uv identified missing minimum Python
  guidance for standalone conductor and a missing fixture-manifest argument in
  a manual example. Both were corrected.
- All 182 installed sdd-spec/conductor files match their sources byte for byte;
  all 182 corresponding deployment hashes match LF-normalized content.
- Source and installed packages contain no .venv, cache directories, bytecode,
  readiness markers or skill-local lockfiles. git diff --check passed.

## Limits

The Windows sandbox still restricts pytest's temporary-directory operations.
Full suites used elevated filesystem access with uv offline. check, snapshot,
interpreter selection and missing-dependency checks passed in the sandbox.
Linux/macOS and full agent behavior evaluations were not run.

The relative cache-dir setting is resolved against the working directory.
The cross-directory probes caught this: --project alone selected the correct
environment but created a second cache. --directory fixes both locations; the
accidental scratch cache was removed. Package installation through APM retained
its existing hidden-character/policy-discovery notices; no successful full APM
security audit is claimed here.
