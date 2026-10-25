# Maintaining sdd-apply

Read this file only when changing the sdd-apply package itself: its instructions,
runtime, tests or dependencies. Applying an approved plan in another project
does not activate these rules or require running this package's tests.

## Test architecture

Keep most scenarios at the execution-engine boundary with fast adapters. Run
the actual transition, validation and acceptance code; replace external I/O.

| Boundary | Scenario tests | Real contract checks |
| --- | --- | --- |
| Git | `tests/memory_repository.py` models commits, indexes, trees and worktrees through `scripts/lib/repository.py`; working files remain real | `native_git`: `git_repository.py`, binary patches, modes, conflicts, hooks and filters |
| State and artifacts | `state_storage.py` and `artifact_storage.py` inject serialized bytes in memory | `native_state`: files, atomic replacement, locks, recovery and external reads |
| Paths | `path_resolution.py` uses a test resolver in temporary workspaces without links; link creation fails loudly | Native cases retain filesystem resolution and containment checks |
| Verification commands | `tests/check_commands.py` executes supported fixture Python checks in process, including assertions and side effects | `native_process` and runner contracts: arguments, shells, exit codes and timeouts |
| Shared document CLI | `tests/shared_commands.py` calls the real CLI entry points in process with isolated imports | Compare results and errors with real Python subprocesses; check uv bootstrap under `installation` |
| Dashboard | Test projections and rendering directly; use real Chrome for browser behavior | Reuse Chrome per worker, with a separate storage context for each test and sequential pages inside that context |

Run shared contracts against both the real and test implementations. Extend
those contracts when an adapter gains behavior. Production defaults must remain
the real implementations; injected factories must be scoped and restored.
Unexpected Git, unsupported commands or unsupported filesystem operations in
fast scenarios must fail rather than silently execute a slower fallback.

Keep state schemas, integrity hashes, event chains, candidate freshness,
evidence validation, ownership and acceptance checks active in scenario tests.
Transfer bytes and object IDs are opaque to orchestration. A test adapter must
not return unconditional success or duplicate the engine's decision rules.

## Fixtures and isolation

Build and validate pristine inputs once per worker. Restore source bytes and
modes before each case, remove extra files, and create independent repository
state and nested data. Native Git cases use independent repository copies.
Use real-engine checkpoints for repeated prerequisites of negative cases;
preserve their paths, event chains, hashes and history. Keep complete positive
lifecycles from initialization to acceptance.

Cache successful parsing by exact input contents, path and work kind; copy
returned mutable data. Changed bytes must invalidate the cache even when size
and timestamps match. Always revalidate document relationships and approvals.
Restore import context after in-process CLI calls.

Keep mutable fixtures, caches and browser contexts local to each pytest worker.
Use worker-owned temporary roots so tests cannot depend on order or alter another
worker's files. Keep environments, bytecode, profiles, worktrees and reports
outside the skill package, following [runtime setup](runtime-setup.md).

## Commands and verification scope

Use **four pytest-xdist workers** (`-n 4`) for normal runs. These are four worker
processes. Pass the count explicitly; do not rely on machine CPU count or an
implicit runner default. Group regression cases by scope to reuse costly
fixtures and keep browser cases together:

```text
uv run --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 4 --dist=loadscope --durations=10
```

For a focused check, replace `tests/` with the affected test file or node ID and
retain `-n 4`. Keep the test path explicit when options have separate values.

| Change or stage | Required checks |
| --- | --- |
| Documentation only | Package links/structure and consistency of affected instructions; use `tests/test_package.py` for the package contract |
| Runtime, test or fixture changes | Relevant focused checks during editing, then the full default regression selection (`not installation`) |
| Final acceptance of runtime, dependency or distribution changes | Regression plus the separate installation selection on the same final revision |

Run installation checks separately with four workers; their independent cases
can use the default distribution:

```text
uv run --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 4 -m installation --durations=10
```

Installation covers source/installed entry points, conflicting consumer projects,
the shared uv CLI, offline and stale-lock failures, and cache restoration. The
`network` case downloads dependencies into empty caches. Retain its evidence;
missing or failed required installation checks leave final acceptance incomplete.
Separate selection does not create a separate time allowance for the same
acceptance run.

## Speed and the stop condition

Keep the complete regression suite capable of finishing within **30 seconds
sequentially**. Four-worker execution is the normal development command; it does
not replace efficient test design. Use `-n 0` only for an explicitly needed
sequential diagnosis or benchmark, and label its results separately.

Measure wall-clock time from command start through exit, including uv, worker
startup, fixture preparation and teardown. Sum commands and retries belonging
to one verification run, including required installation checks. Report the
selected groups, worker count, result counts and total elapsed time. Worker
durations are diagnostic data, not elapsed time for the run.

**If the cumulative run exceeds 30 seconds for any reason, stop the current
work and its running test processes immediately.** Report commands, elapsed time
and any known cause; recommend optimizing the tests before continuing. Await a
new user instruction. Network access, dependency installation, failures and
retries do not exempt the run. Do not drop cases, reset the timer by splitting
commands, increase worker count or keep retrying to bypass this stop condition.

When test optimization is authorized, first inspect fixture setup and the
slowest cases (`--durations=0` includes setup timings). Remove repeated I/O and
process startup, reuse validated prerequisites, and concentrate heavy checks
at adapter boundaries. Preserve regression coverage and real contracts. Finish
with the required full selection, package-cleanliness check and recorded timing.
