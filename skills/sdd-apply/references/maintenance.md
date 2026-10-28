# Maintaining sdd-apply

Read this file only when changing the sdd-apply package itself: its instructions,
runtime, tests or dependencies. Applying an approved plan in another project
does not activate these rules or require running this package's tests.

## Test architecture

Keep most scenarios at the execution-engine boundary with fast adapters. Run
the actual transition, validation and acceptance code; replace external I/O.

Before adding a real browser, Git, filesystem, network or subprocess test,
identify the concrete failure that cheaper tests cannot detect. Record that
reason beside the test and use an existing adapter contract when it already
covers the risk. Add a new integration case only when this gap is established;
exercise combinations of domain rules through the fast adapters.

Prioritize execution, evidence integrity and acceptance behavior over eval
environment setup. Keep eval infrastructure tests to the minimum contracts for
version/dependency isolation, exclusion of grading answers, and rejection of
invalid evidence. Test scenario matrices and repetition counts without creating
workspaces. Materialize one representative per distinct filesystem behavior;
reuse pristine synthetic evidence instead of rebuilding it for each rejection.

| Boundary | Scenario tests | Real contract checks |
| --- | --- | --- |
| Git | `tests/memory_repository.py` models commits, indexes, trees and worktrees through `scripts/lib/repository.py`; checkpoint rule scenarios use an explicit working-file map | `native_git`: `git_repository.py`, binary patches, modes, conflicts, hooks and filters |
| State and artifacts | `state_storage.py` and `artifact_storage.py` inject serialized bytes in memory | `native_state`: files, atomic replacement, locks, recovery and external reads |
| Paths | `path_resolution.py` uses a test resolver in temporary workspaces without links; link creation fails loudly | `native_paths`, `native_git` and installation retain filesystem resolution and containment checks |
| Verification commands | `tests/check_commands.py` executes supported fixture Python checks in process, including assertions and side effects | `native_process` and runner contracts: arguments, shells, exit codes and timeouts |
| Shared document CLI | `tests/shared_commands.py` calls the real CLI entry points in process with isolated imports | Compare results and errors with real Python subprocesses; check uv bootstrap under `installation` |
| Dashboard | Test projections and rendering directly; use real Chrome for browser behavior | Reuse Chrome per worker, with a separate storage context for each test and sequential pages inside that context |

Use [conftest.py](../tests/conftest.py) for adapter selection and
[pytest.ini](../tests/pytest.ini) for registered markers and the default selection.
Select real boundaries independently: `native_git` also retains OS path
resolution, but leaves state storage and check commands on fast adapters.
`native_state` and `native_process` do not enable real Git or OS path resolution;
add `native_paths` for filesystem-link behavior. Combine markers when a test
crosses several real boundaries. `installation` selects real Git, storage,
paths and check processes. The shared CLI adapter stays injected even
under `installation`; use the original callable returned by `shared_cli` when
the contract needs the actual uv entry point.

The fast resolver covers both the runtime resolver and `Path.resolve` inside
the test temporary root. Paths outside that root still use the OS. Keep fixture
checks sequential within each worker: their adapters temporarily replace cwd,
argv, streams and import context. Use xdist processes for concurrency.

Run shared contracts against both the real and test implementations. Extend
those contracts when an adapter gains behavior. Production defaults must remain
the real implementations; injected factories must be scoped and restored.
Unexpected Git, unsupported commands or unsupported filesystem operations in
fast scenarios must fail rather than silently execute a slower fallback.

Keep state schemas, integrity hashes, event chains, Git cleanliness,
evidence validation, ownership and acceptance checks active in scenario tests.
For state storage changes, verify bounded manifest growth, deduplication, lazy
reads, full-history audit, idempotent lookup and interruption before manifest
replacement against both storage adapters. See [state storage](state-storage.md).
Cover detached sealed manifests, rejected or interrupted writes, object
tampering between audits, and commands that succeed while changing working
files. Reuse a checked source only within the same operation when no command
or writer intervenes; read it afresh after commands and at later evidence gates.
Transfer bytes and object IDs are opaque to orchestration. A test adapter must
not return unconditional success or duplicate the engine's decision rules.

## Fixtures and isolation

Build and validate pristine inputs once per worker. Restore source bytes and
modes before each case, remove extra files, and create independent repository
state and nested data. Native Git cases use independent repository copies.
Use real-engine checkpoints for repeated prerequisites of negative cases;
build only through the requested stage, cache it per worker and restore the
last prepared state before advancing after a test. Preserve paths, event chains,
hashes and history. Keep complete positive lifecycles from initialization to
acceptance. Keep fixture checkpoints confined to synthetic temporary workspaces.
Use the commit and current-change document boundary from
[source identity](state-storage.md#source-identity) for execution evidence.

Restore serialized state/artifact bytes, independent nested repository data,
directory indexes and empty directories with each checkpoint. Index immediate
children so listing one directory does not scan all stored objects. Memoize
lexical containment and namespace ownership only inside the memory adapter;
invalidate ownership on root registration and clear both caches on root reset.
Keep task views independent and lazy instead of serializing their full history.
For long-history lookup tests, prepare authentic events in memory and publish
their bytes to the tested store; retain real transaction, crash and audit tests.

Native Git fixtures need empty `hooks` and `info` directories, but no sample
hooks copied from Git's template.

Use `Checkpoint.restore(..., memory_worktree=True)` for repeated rule scenarios
whose repository edits are explicit inputs. Arrange those edits with
`repository_support.write_file` / `remove_file`, then stage and commit as needed.
Status and owned trees must derive from the independent byte map, without disk
scans or a constant clean-status stub. The existing shared repository contracts
cover exclusions, staging, deletion, ignored paths and modes; their memory
variant rejects disk scans and byte reads.

This option replaces the repository working-tree boundary only. Checkpoint
restoration, specification reads and executable check fixtures still use real
files. Keep the disk working tree for tests of check-command side effects,
source mutations, patch materialization and worktree lifecycle. Use those
representative contracts to cover external changes instead of repeating them
for every registry, permission, evidence-identity or procedure-state variant.

Cache successful parsing by exact input contents, path and work kind; copy
returned mutable data. Changed bytes must invalidate the cache even when size
and timestamps match. Always revalidate document relationships and approvals.
Re-raise invalid input through the active parser rather than caching exceptions
from another imported module. Reuse CLI imports by fixed fixture installation
root; changes to dependency code require a new fixture root. Restore import
context after each in-process call instead of fingerprinting package files.

Keep mutable fixtures, caches and browser contexts local to each pytest worker.
Use worker-owned temporary roots so tests cannot depend on order or alter another
worker's files. Keep environments, bytecode, profiles, worktrees and reports
outside the skill package, following [runtime setup](runtime-setup.md).

## Commands and verification scope

Use the interpreter and external uv directories established by
[runtime setup](runtime-setup.md). Substitute absolute paths for `<python>` and
`<skill-root>` below; reuse that interpreter across measurements.

Use **four pytest-xdist workers** (`-n 4`) for normal full runs. These are four worker
processes. Pass the count explicitly; do not rely on machine CPU count or an
implicit runner default. Group regression cases by scope to reuse costly
fixtures and keep browser cases together:

```text
uv run --compile-bytecode --python "<python>" --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 4 --dist=loadscope --durations=10
```

For several independent focused cases, replace `tests/` with the affected file
or node IDs and use `-n 4 --dist=load`. For one case or a small documentation
check, use `-n 0` to avoid worker startup. `loadscope` assigns module-level tests
from one file to one worker; worker count alone does not prove concurrent work.
When diagnosing scheduling, inspect case assignments and fixture scope. Keep
browser cases together to preserve one browser process per module and worker.
Keep the test path explicit when options have separate values.

The runner uses Python-level capture (`--capture=sys`); subprocess contracts
capture their own streams. Request descriptor capture explicitly when testing
output written directly to OS file descriptors.

| Change or stage | Required checks |
| --- | --- |
| Documentation only | Package links/structure and consistency of affected instructions; use `tests/test_package.py` for the package contract |
| Runtime, test or fixture changes | Relevant focused checks during editing, then the full default regression selection (`not installation`) |
| New or expanded tests | Full default selection with `-n 0`; accept the additions only when total wall time is at most 60 seconds |
| Final acceptance of runtime changes | Full default regression selection (`not installation`); installation is outside this run |
| Dependency or distribution changes | Separate installation verification when that scope is requested; retain its evidence independently |

Installation checks are a separate verification scope, not an automatic second
command in the regression run. When requested, run them with four workers;
their independent cases can use the default distribution:

```text
uv run --compile-bytecode --python "<python>" --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 4 -m installation --durations=10
```

Installation covers source/installed entry points, conflicting consumer projects,
the shared uv CLI, offline and stale-lock failures, and cache restoration. The
`network` case downloads dependencies into empty caches. Retain its evidence;
missing or failed requested installation checks leave that verification scope
incomplete. Splitting one run into component commands does not reset its time
allowance.

## Speed and the stop condition

**Make total suite time an acceptance condition for every new test.** After
adding or expanding tests, measure the full default selection sequentially.
Accept the additions only when all required tests pass within 60 seconds,
including environment and fixture preparation. If the limit is exceeded,
redesign the new test and its prerequisites or discard redundant coverage;
preserve required behavioral coverage. A baseline already over budget requires
optimization before accepting more tests. Record the exact command, selection
and total elapsed time. A focused pass, exit code zero, or parallel run does not
satisfy this gate. Explicit authorization to run long optimization experiments
permits measurement; it is not evidence that the timing target was achieved.

Keep the full default regression selection capable of finishing within **60 seconds
sequentially**. Four-worker execution is the normal development command; it does
not replace efficient test design. Use this command for a sequential benchmark:

```text
uv run --compile-bytecode --python "<python>" --locked --script "<skill-root>/scripts/test.py" tests/ -q -n 0 --durations=10
```

Use uv's `--compile-bytecode` to prepare installed dependencies in its external
cache. Include that preparation in wall time, including the first run. Skill
entry points still disable bytecode writes in source and installed packages.
Record cold dependency preparation separately from reuse of an existing cache.
Diagnostic plugins that write a report for each phase add their own I/O; use
the ordinary command with `--durations` for the final wall-clock measurement.

Measure wall-clock time from command start through exit, including uv, worker
startup, fixture preparation and teardown. Include dependency installation,
downloads and bytecode preparation whenever the command performs them, including
ordinary regression runs. Sum component commands and internal retries belonging to one verification
run. A new invocation after the previous run finishes or is stopped receives a fresh 60-second limit; do not carry elapsed time across runs. The separate installation selection is a set of tests, not permission to
exclude environment setup from timing. Report the command, selection, worker
count, passed/skipped/deselected counts, cache condition and total elapsed time.
Worker durations are diagnostic data, not elapsed time for the run. Check Chrome
availability when browser coverage is required; a skip is not a passing browser
check. Keep measured timings in external reports, not as fixed guarantees here.

**If the cumulative run exceeds 60 seconds for any reason, stop the current
work and its running test processes immediately.** Report commands, elapsed time
and any known cause; recommend optimizing the tests before continuing. Await a
new user instruction. Network access, dependency installation, failures and
retries do not exempt the run. Do not drop cases, reset the timer by splitting
commands or increase worker count to bypass this stop condition. A fresh limit for a later run does not waive the requirement to await a new user instruction after an overrun.

When test optimization is authorized, first inspect fixture setup and the
slowest cases (`--durations=0` includes setup timings). Remove repeated I/O and
process startup, reuse validated prerequisites, and concentrate heavy checks
at adapter boundaries. Preserve regression coverage and real contracts. Finish
with the required full selection, package-cleanliness check and recorded timing.
