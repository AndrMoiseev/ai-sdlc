# Runtime setup

## Installation

Install the aisdlc-core bundle with its sibling SDD skill folders. For manual
deployment copy the complete bundle. Follow [shared runtime setup](../../sdd-shared/references/runtime-setup.md)
for discovery, API v1 compatibility and external cache storage. `sdd_shared` selects
an explicit dependency root. Legacy `sdd_spec` selects its sibling sdd-shared.
Keep execution directories when updating; old bases remain readable without rewriting.

## Preflight and recovery

Check `uv --version`, `uv cache dir`, Git, the actual host's fresh-context tools, writable project storage, and local Git author/committer identity before admitting tasks. Resolve the installed skill root; verify `scripts/execute.py` and its adjacent lockfile. Locate the complete compatible `sdd-shared` package through the input API, or pass its explicit root. Missing dependencies or host capabilities produce a concrete blocker.

Run every Python entry point with its own PEP 723 metadata and shipped lockfile:

```text
uv run --locked --script "<skill-root>/scripts/execute.py" --request "<absolute-request.json>"
uv run --locked --script "<skill-root>/scripts/test.py" <test-path> -q -m "not network"
```

Apply the shared runtime requirements to both entry points. Keep worktrees outside
skill collections and retained reports in the execution directory. Unit tests do
not replace actual host or browser runs.

## Test runs

This section applies only to development and acceptance of changes to the
sdd-apply skill package itself. Using sdd-apply to implement or accept changes
in another project does not require running the skill's bundled tests.

| Verification stage | Required selection |
| --- | --- |
| Individual tasks modifying sdd-apply: baseline, self-check, independent verification, integration and repair loops | Local regression with `-m "not network"`. |
| Final acceptance of changes to the sdd-apply skill itself | Local regression plus the dependency download/cache-restoration test on the final HEAD of those skill changes, or the complete suite without a marker filter. |

Run `test_first_run_and_cache_restoration` (marked `network`) only at final
acceptance of changes to sdd-apply itself, not for each development task.
It checks installation and restoration of the
package environment; repeated downloads add network latency to task feedback.
Retain its raw log and result with final-acceptance evidence. If the final HEAD
changes after a repair, repeat final acceptance against the new HEAD. A failed
or unavailable dependency check leaves final package acceptance incomplete.

For each task's local regression loop, run eight isolated pytest workers:

```text
uv run --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 8 --dist worksteal -m "not network" --durations=10
```

This selection includes real Git/worktree, browser, installed-copy, offline and
stale-lock checks. It excludes one `network` test that downloads dependencies
twice into an empty uv cache. Its live-index latency has no fixed upper bound
below the subprocess timeout, so report this selection as local regression,
not complete package verification. The minute target assumes uv and the locked
test dependencies are already installed; initial downloads are additional work.

At final acceptance of changes to the skill itself, run the network check alongside
fresh local regression, or omit the marker filter to run the complete suite:

```text
uv run --locked --script "<skill-root>/scripts/test.py" tests/ -q -m network --durations=10
uv run --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 8 --dist worksteal --durations=10
```

Keep `tests/` explicit when passing options with separate values. Workers build
and validate one pristine repository each. Every test receives independent file,
Git and nested basis copies; tests of changed inputs still invoke real validation.
Fixture-contract tests compare copied inputs with fresh validation and check
mutation isolation. Browser profiles remain separate. Worker imports and pytest
temporary files stay outside the skill package.

On Git for Windows, the runner prefers `mingw64/bin/git.exe` next to the detected
`cmd/git.exe` launcher, avoiding an extra process for every Git command. This only
changes PATH for the test process and its children. Other Git layouts retain the
normal PATH lookup. Start with eight workers on a 16-thread machine; more workers
can increase contention, so compare wall time before increasing the count.

Parallel execution is opt-in; omitting `-n` keeps the sequential behavior.
Use `-n 0` for an explicit sequential diagnostic run. For a focused change, pass a test file
or node ID, for example `tests/test_state.py -q --durations=10`. Run the complete
suite before claiming full verification. Use `--durations=0` to include fixture
setup timings when investigating another slowdown.

Native role tools use the host session. A CLI fallback requires a version/login probe, a read-only fresh-session probe, and verified workspace access. Do not infer an API-key requirement from another harness. Preserve sandbox enforcement and record unavailable checks honestly.
