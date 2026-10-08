# Start an execution

1. Resolve the selected change and actual user instruction. Use the public `validate` operation to inspect readiness without changing normative files. Missing or invalid approvals, unresolved blocking questions, ambiguous ownership, or incompatible sdd-spec stop admission. Return specification work to sdd-spec.
2. Check local execution branch, HEAD, Git identity, pre-existing staged/unstaged/untracked work, and commit capability. Preserve existing work. Execution authorization includes local task commits; it does not authorize mixing unrelated changes into them.
3. Invoke `initialize` with validated input arguments and the actual orchestrator identity. For an existing execution use resume instead. Preserve the original user instruction and mode decision. The script captures basis and baseline and generates the initial dashboard before any task starts.
4. Read the saved state and show the dashboard link using [progress](../references/progress.md). Return to the router to load the one selected mode. Continue authorized tasks autonomously until completion or a concrete blocker.
