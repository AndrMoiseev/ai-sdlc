# Independent implementation review

Reviewed 2026-10-08 against `sdd/changes/sdd-execution-skill/tasks.md` and `design.md`, applying repository AGENTS.md, conductor, SOP principles and package-runtime requirements. Package sources were read-only for this reviewer; the implementing agent applied fixes concurrently. Findings below distinguish the initial reproduction from the latest verification.

## Final recheck

All six findings below are resolved in the reviewed implementation. Retained regression tests now live in `skills/sdd-apply/tests/test_review_regressions.py`, the only package file this reviewer was authorized to add. The final run passed **7 tests in 24.70s**. These are deterministic unit/integration fixtures with synthetic host attestations, not fresh-agent behavior evidence.

The cleanup protection now rejects an unknown ignored file without deleting it. Removal recovery was tested at both crash boundaries: immediately after successful Git removal (prepared journal) and before atomic state replacement (observed journal). Replaying the identical event reconciles the missing worktree, marks it removed, and advances the state exactly once.

## Cleanup findings — resolved

### P1 — Cleanup destroys unknown ignored files

`skills/sdd-apply/scripts/lib/worktrees.py:35` compares the transfer snapshot before `git worktree remove --force` at line 38. `common.py:70` builds snapshots using `git ls-files --cached --others --exclude-standard`, so ignored files are absent from both sides. After a fully verified, committed and accepted parallel task, add `*.local` to the repository's `.git/info/exclude`, then write `user-data.local` inside its worktree. The cleanup succeeds and deletes those untransferred bytes.

Reproduced by `review_tests/test_defects.py::test_cleanup_deletes_unknown_ignored_user_data`: **1 passed, 4 deselected in 4.72s**. Here passing deliberately proves the unwanted deletion. Existing `test_worktrees.py` checks preservation of an unaccepted nonignored file, so it misses this accepted-worktree case.

Resolution verified: complete file inventory includes ignored paths and is compared against the transfer inventory; transfer/cleanup also check task ownership. The retained test now asserts refusal and preservation of the file's bytes.

### P2 — Worktree removal has no recoverable external-effect journal

`skills/sdd-apply/scripts/lib/worktrees.py:38-40` removes the worktree and only then returns state updates. Unlike creation, it never records `intent`/`observed`. A crash in `state.write_json` after successful Git removal leaves `removed` unset. Replaying the same event reaches line 35 and invokes a Git snapshot in the now absent directory, preventing reconciliation.

Initially a static finding. Resolution now verified with two executed crash probes: removal records a durable intent and replay reconciles the missing directory against Git registration before attempting a snapshot. Both prepared and observed journal recovery passed.

## Resolved during review

1. **P1 — An older green check masked a later failure.** `verification.py:30` originally selected any passing evidence for the candidate. An independent pass followed by a failed run still allowed review, commit and acceptance. Original probe reproduced this. Latest implementation selects the latest evidence and rejects the failed outcome. Rechecked successfully. The failing command result is injected at the command adapter for deterministic simulation; this is not a live agent evaluation.
2. **P1 — Noncanonical ownership paths bypassed baseline overlap checks.** `commits.py:23-32` looked up the raw ownership string in the baseline. `./check.py` and directory paths bypassed file-level comparison. Initial helper-level probe reproduced the bypass. The full event probe now rejects `./check.py` at start; directory rejection is present in the same guard. Canonical file paths are now required. Rechecked the alias rejection successfully.
3. **P1 — Final acceptance could certify uncommitted implementation.** After task acceptance, modifying its owned file and running a fresh final check previously produced `complete`, although `HEAD` still contained the old bytes. `finalize.py:18` now compares an index tree of owned files to final HEAD. Rechecked: result is `partial`.
4. **P1 — Lost reviewer replacement could not finish its reserved round.** A successor registered after a lost reviewer could neither reserve a new round (`active_review` already set) nor finish the existing round (`active_reviewer` still old role). `resume.py:113-114` now reassigns the active reviewer without consuming another round. Rechecked: successor completes the existing round.

Intermediate fixed-regression run: **4 passed, 1 deselected in 10.05s**. Final package regression run: **7 passed in 24.70s**.

## Reproduction and limits

Run the retained package regressions from any directory using the absolute script path below:

```powershell
$env:UV_CACHE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) 'uv-runtime/cache'
uv run --locked --script C:/Users/Andrew/repos/ai-sdlc/skills/sdd-apply/scripts/test.py tests/test_review_regressions.py -q
```

The first sandboxed attempt failed because pytest could not create its nested system-temp directory. The standard permission mechanism allowed the subsequent temporary-fixture runs. The command uses the bundled PEP 723 metadata and lock, external uv cache, disabled bytecode and disabled pytest cache. This reviewer added only the authorized package regression test file; implementation fixes were made by the implementing agent.

All host role records in these probes are synthetic unit-test attestations. They establish deterministic state/Git behavior, not actual fresh-agent execution. This review did not perform the full installation/runtime matrix or claim completion of the behavioral acceptance criteria. Original exploratory probes outside the package are historical reproduction artifacts; the package regression tests encode the corrected behavior.
