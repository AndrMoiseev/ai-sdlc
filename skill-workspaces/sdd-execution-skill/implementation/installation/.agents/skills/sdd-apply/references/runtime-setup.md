# Runtime setup

## Installation

The repository's `aisdlc-core` APM package includes `sdd-spec` and `sdd-apply`.
Use the repository's documented APM installation from the consuming project.
For a manual install, copy both complete skill folders into the same supported
skill collection; preserve scripts, adjacent locks, assets and agent metadata.
Keep existing execution directories when updating a skill. Dependency discovery
checks the sibling package first; `sdd_spec` selects an explicit compatible copy.
Installation adds no Python dependency to the consuming project.

## Preflight and recovery

Check `uv --version`, `uv cache dir`, Git, the actual host's fresh-context tools, writable project storage, and local Git author/committer identity before admitting tasks. Resolve the installed skill root; verify `scripts/execute.py` and its adjacent lockfile. Locate the complete compatible `sdd-spec` package through the input API, or pass its explicit root. Missing dependencies or host capabilities produce a concrete blocker.

Run every Python entry point with its own PEP 723 metadata and shipped lockfile:

```text
uv run --locked --script "<skill-root>/scripts/execute.py" --request "<absolute-request.json>"
uv run --locked --script "<skill-root>/scripts/test.py" <test-path> -q
```

Use absolute script and request paths outside their directories. uv installs missing dependencies and restores its environment after cache cleanup; the consuming project needs no Python manifest, dependency edits, virtual environment, or sync step. Report actual network, permissions, and stale-lock errors. Use normal host permission mechanisms. Add `--offline` only for explicitly requested offline execution; update locks only as an explicit dependency change.

Keep caches, environments, bytecode, test artifacts, and worktrees outside source and installed skill collections. On Windows verify the inherited user `UV_CACHE_DIR` points to `uv-runtime/cache` under system temporary storage; `UV_TOOL_DIR` uses its `uv-runtime/tools` sibling for third-party uvx. These stores are disposable; retained reports belong in the execution directory or an explicit external workspace. Check actual write access rather than assuming it from an environment variable.

Keep PEP 723 and `<script>.lock` beside each distributed entry point, including standard-library scripts. Disable bytecode before local imports; use `sys.executable` and `-B` for Python children; disable pytest caching or place it externally. Package verification covers first and repeated runs from source and installed copies, unrelated cwd, conflicting consumer dependencies, empty-cache offline failure, stale-lock failure, unchanged locks, and hidden/ignored package contents. Unit tests do not replace actual host or browser runs.

Native role tools use the host session. A CLI fallback requires a version/login probe, a read-only fresh-session probe, and verified workspace access. Do not infer an API-key requirement from another harness. Preserve sandbox enforcement and record unavailable checks honestly.
