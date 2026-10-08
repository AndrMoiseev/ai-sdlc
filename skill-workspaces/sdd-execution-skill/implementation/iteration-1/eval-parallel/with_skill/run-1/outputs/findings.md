# Parallel evaluation findings (in progress)

No source-package change made by this evaluator. The accepted fixture contains two independent numeric-add tasks, separate AC ownership, isolated detached worktrees and task-specific files. Dependencies are source-referenced, not hermetically copied.

Observed author defect: Windows UTF8 BOM on new standard-library PEP723 scripts led uv to warn that --locked had no effect outside a project. Both scripts were normalized without BOM through reserved repairs, locks regenerated, and full self/independent checks rerun. Warning disappeared in both observed repaired runs. No test weakening or hidden retry occurred.

Observed orchestrator mistakes, retained in raw logs: initial synthetic fixture duplicate AC owners rejected; invalid host enum codex-native rejected; reviewer B integrated packet registered prematurely and therefore stale, explicitly corrected with current-state assignment before substantive review. These are not labeled source-package defects.

Native host constraints: followup can report thread limit despite a completed sibling slot while root microtest occupies the fourth slot. Parent paused microtests, preserving real role independence. Full native transcripts remain in host session; transcribed launch index and raw API logs are retained locally. No synthetic role launch claimed.
