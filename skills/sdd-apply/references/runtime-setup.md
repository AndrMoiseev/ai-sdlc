# Runtime setup

## Installation

Install the aisdlc-core bundle with its sibling SDD skill folders. For manual
deployment copy the complete bundle. Follow [shared runtime setup](../../sdd-shared/references/runtime-setup.md)
for discovery, API v1 compatibility and external cache storage. `sdd_shared` selects
an explicit dependency root. Legacy `sdd_spec` selects its sibling sdd-shared.
Keep execution directories when updating. Execution state uses schema version 2;
older state requires an explicit, backed-up conversion before execution resumes.

## Preflight and recovery

Check `uv --version`, `uv cache dir`, Git, the actual host's fresh-context tools, writable project storage, and local Git author/committer identity before admitting tasks. Resolve the installed skill root; verify `scripts/execute.py` and its adjacent lockfile. Locate the complete compatible `sdd-shared` package through the input API, or pass its explicit root. Missing dependencies or host capabilities produce a concrete blocker.

Run every Python entry point with its own PEP 723 metadata and shipped lockfile:

```text
uv run --locked --script "<skill-root>/scripts/execute.py" --request "<absolute-request.json>"
```

Apply the shared runtime requirements to runtime entry points. Keep worktrees outside
skill collections and retained reports in the execution directory. Unit tests do
not replace actual host or browser runs.

Native role tools use the host session. A CLI fallback requires a version/login probe, a read-only fresh-session probe, and verified workspace access. Do not infer an API-key requirement from another harness. Preserve sandbox enforcement and record unavailable checks honestly.

## Transient execution files

Before `initialize` or resuming execution, ensure the original project root's
`.gitignore` excludes execution directories:

```gitignore
/sdd/changes/*/execution/
```

Create `.gitignore` if absent; preserve existing entries and avoid duplicate rules.
For a change outside `sdd/changes/`, add its project-relative execution directory
instead. Verify the actual execution path with `git check-ignore` before generating
state or reports; account for any negation rules that override the exclusion.
Keep execution files locally for recovery, dashboards and evidence, and keep them
out of commits because they are transient and can grow beyond Git hosting limits.
Report any execution files already tracked by Git: adding an ignore rule does not
remove them from the index or existing history.
