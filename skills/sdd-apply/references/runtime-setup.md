# Runtime setup

## Installation

Install the aisdlc-core bundle with its sibling SDD skill folders. For manual
deployment copy the complete bundle. Follow [shared runtime setup](../../sdd-shared/references/runtime-setup.md)
for discovery, API v1 compatibility and external cache storage. `sdd_shared` selects
an explicit dependency root. Legacy `sdd_spec` selects its sibling sdd-shared.
Keep execution directories when updating; old bases remain readable without rewriting.

## Preflight and recovery

Check `uv --version`, `uv cache dir`, Git, the actual host's fresh-context tools, writable project storage, and local Git author/committer identity before admitting tasks. Resolve the installed skill root; verify `scripts/execute.py` and its adjacent lockfile. Locate the complete compatible `sdd-shared` package through the input API, or pass its explicit root. Missing dependencies or host capabilities produce a concrete blocker.

Run every Python entry point with its own PEP 723 metadata and shipped lockfile:

```text
uv run --locked --script "<skill-root>/scripts/execute.py" --request "<absolute-request.json>"
uv run --locked --script "<skill-root>/scripts/test.py" <test-path> -q
```

Apply the shared runtime requirements to both entry points. Keep worktrees outside
skill collections and retained reports in the execution directory. Unit tests do
not replace actual host or browser runs.

Native role tools use the host session. A CLI fallback requires a version/login probe, a read-only fresh-session probe, and verified workspace access. Do not infer an API-key requirement from another harness. Preserve sandbox enforcement and record unavailable checks honestly.
