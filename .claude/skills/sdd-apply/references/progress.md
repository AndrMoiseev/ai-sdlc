# Progress and derived views

Use the `dashboard` operation to regenerate `summary.md`, `technical-debt.md`, `dashboard.html`, and `dashboard-state.js` from execution state. The technical debt journal preserves recommendations from all recorded review rounds with stable finding IDs, task IDs, paths, problems, and proposed fixes. Regenerate it after each review; never hand-edit this derived journal. The initial dashboard exists before task admission. Provide its local link at start and when reporting completion or a blocker.

Open the HTML from disk first. It includes a retained snapshot and polls adjacent generated data without page reload; the visible revision and timestamp distinguish live progress from a saved snapshot. Inspect task states, evidence stages, both budget counters, blockers, commits and log links against state. A stale or inaccessible view is not evidence that the state changed.

If the browser cannot load local updates, use the script's loopback-only `serve` operation. Retain its returned ownership information; stop only this run's server with `stop_server`. Do not open public interfaces or terminate unrelated processes.

If state succeeded but view generation failed, run `dashboard` again. Preserve the accepted state and commit: regenerating HTML must not replay implementation or Git operations. Neither a manually edited summary nor dashboard grants acceptance.
