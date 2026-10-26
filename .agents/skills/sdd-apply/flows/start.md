# Start an execution

Read [start API](../references/api-start.md); use installed operation help for request fields.

1. Resolve the selected change and actual user instruction. Use the public `validate` operation to inspect readiness without changing normative files. Missing or invalid approvals, unresolved blocking questions, ambiguous ownership, or incompatible sdd-shared stop admission. Return specification work to sdd-spec.
2. Check local execution branch, HEAD, Git identity, pre-existing staged/unstaged/untracked work, and commit capability. Preserve existing work. Execution authorization includes local task commits; it does not authorize mixing unrelated changes into them.
3. Invoke `initialize` with validated input arguments and the actual orchestrator identity. Pass `isolation: true` after verifying task worktrees; omit `mode` for the parallel default or pass `mode: "sequential"` for the user's explicit choice. Both modes require isolation. If worktrees are unavailable, report the blocker before implementation. For an existing execution use resume instead. The script captures basis and baseline and generates the initial dashboard before any task starts.
4. Read the saved state and show the dashboard link using [progress](../references/progress.md). Return to the router to load the one selected mode. Continue authorized tasks autonomously until completion or a concrete blocker.
