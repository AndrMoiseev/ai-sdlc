# Progress and derived views

Use the `dashboard` operation to regenerate `summary.md`, `technical-debt.md`, `dashboard.html`, and `dashboard-state.js` from execution state. The technical debt journal preserves recommendations from all recorded review rounds with stable finding IDs, task IDs, paths, problems, and proposed fixes. Regenerate it after each review; never hand-edit this derived journal. The initial dashboard exists before task admission. Provide its local link at start and when reporting completion or a blocker.

Open the HTML from disk first. It includes a retained snapshot and polls adjacent generated data without page reload; the visible revision and timestamp distinguish live progress from a saved snapshot. Inspect task states, evidence stages, both budget counters, blockers, commits and log links against state. A stale or inaccessible view is not evidence that the state changed.

Read waves as planned parallel groups with identical task dependencies and no pairwise `cannot_parallel_with` restriction. Each wave lists the tasks whose acceptance enables its members; waves can overlap. Membership and numbering derive from the approved plan, remaining stable across status updates. Runtime file/resource conflicts appear as wait reasons without regrouping; executor capacity and launch checks still govern actual overlap. Integration remains sequential. Use `available` and the admission operations to launch work; a wave's position or ready label does not grant admission. Follow dependency links to inspect the required tasks, and keep the execution state as the source of truth.

If the browser cannot load local updates, use the script's loopback-only `serve` operation. Retain its returned ownership information; stop only this run's server with `stop_server`. Do not open public interfaces or terminate unrelated processes.

Expanded evidence preferences are browser-local and scoped to the page path, change and run. They survive data updates and page reloads; when browser storage is unavailable, evidence stays visible without a disclosure control. These preferences do not change execution state.

If state succeeded but view generation failed, run `dashboard` again. Preserve the accepted state and commit: regenerating HTML must not replay implementation or Git operations. Neither a manually edited summary nor dashboard grants acceptance.

For refactoring, show accepted tasks separately from confirmed whole criteria.
The whole-result panel reports current evidence gaps and retired checks with
confirmed reasons. Contributions and accepted task counts do not establish the
whole result. A changed integrated HEAD, manifest or applicable registry removes
old confirmation from the current projection; historical logs remain available.

Ordinary executions with an additional final registry show a separate final project
checks panel (`final_project_checks` in compact and dashboard data). Its confirmed
criteria describe only those project checks. Accepted task counts and task final
evidence remain separate requirements; either missing set blocks final completion.
