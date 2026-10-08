# Native parallel end-to-end evaluation

Result: successful native parallel execution, followed by a separate expected fail-closed final-verification scenario. Seven evidence assertions passed; grading is an orchestrator assessment, not blinded.

Two fresh executor contexts implemented independent finite-add tasks in registered detached worktrees. Their active implementation turns overlapped. Fresh independent verifier contexts recorded baseline planned absence, then real self/independent checks, reserved worktree review, serialized script-owned binary transfer/integration, fresh integration evidence and a second reserved review. No executor created commits.

| Task | Local task commit | Final independent check |
|---|---|---|
| TASK-add | b4452b04d79810b7eff7d5ba2b72aa5bf8a65c95 | 5 tests / 49 cases, exit 0 |
| TASK-alternate | 4252002de7f6c04dab478c8b1bc89c2071f0e702 | 4 tests / 39 cases, exit 0 |

Both fresh final verifiers tested final HEAD `4252002de7f6c04dab478c8b1bc89c2071f0e702`. All three AC were accepted, missing criteria empty, result complete. Each task used two of three lifetime review rounds; zero failed-test repair cycles. Both task worktrees were safely removed after acceptance and role completion. Normative basis stayed unchanged. The complete successful snapshot is `success-state.json`, raw execution evidence and generated dashboard are under `success-execution/`, and compact results are `success-summary.json`.

Observed Windows fixture repair: both generated standard-library PEP723 scripts initially had a UTF8 BOM and uv emitted a --locked warning. Evidence-backed author repairs removed only BOM and regenerated locks. Actual full checks were rerun on changed candidates; the warning disappeared. These were fixture-author fixes, not source-package changes. Original logs remain retained.

For the separate negative scenario, success evidence was copied first. Supported resume reopened the disposable run; a new fresh final verifier was registered. The required `check.py` was temporarily moved to an external backup. Actual final check returned unavailable, ran no tests and did not retry. Finalize returned partial/blocked. Evidence is `negative/verifier.json`, `negative/state.json`, and `negative/execution/`. The file was restored byte-for-byte; git diff of all six task-owned paths against HEAD is empty. Recorded partial state intentionally remains; it was not rewritten to completed. This expected negative result does not alter the preserved prior success snapshot.

No source skill files or normative docs were changed by this evaluator. Native launch/result index: `native-trace.md`; real role outputs: `exec-*-report.json`, `verify-*.json`, `integration-*.json`, `review-*.json`, `final-*.json`. API requests, responses, stderr and measured timings are retained adjacent. Total success duration was 1570.05 seconds; token counts are unavailable/null. Negative timing is separate.

Limitations: external temporary fixture and worktrees isolate project paths but native contexts inherit the host skill catalog and shared filesystem permissions. Complete dependency skills were source-referenced via absolute paths; this is not a hermetic installed-copy comparison or a no-skill control. Full native conversation transcripts remain in the host; local launch index is a faithful transcription, not a complete raw export. Assertions were documented during final verification, not preregistered. Dashboard generation/state were retained; browser interaction was not repeated in this run. One integrated-review packet was registered prematurely, detected as stale by reviewer, and explicitly superseded by current-state candidate assignment before review. Invalid initial fixture ownership and host enum attempts were rejected and retained. No source-package correctness defect was established by this scenario.
