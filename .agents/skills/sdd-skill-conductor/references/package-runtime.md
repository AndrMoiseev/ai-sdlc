# Runtime state outside the skill package

Apply these requirements when creating a skill, changing runtime commands,
or reviewing it for installation or packaging. Installers can copy entire
skill directories, including files ignored by Git.

## Design and document the runtime

1. Keep source code, resources and dependency declarations in the package.
   Keep environments, caches, bytecode and generated results outside source
   and installed skill collections, including skills/, .agents/skills/ and
   .claude/skills/.
2. Make authored Python entry points standalone uv scripts. Declare Python
   requirements and dependencies using PEP 723, including `dependencies = []`
   for standard-library scripts. Create and ship each adjacent `<script>.lock`
   with `uv lock --script "<script>"`. The consuming project needs no Python
   manifest, lockfile, dependency additions or environment preparation.
3. Let uv manage isolated script environments in its user cache. Use the
   once-per-user `UV_CACHE_DIR` setting for writable external storage; on Windows
   the agreed location is `uv-runtime/cache` under the system temporary directory.
   `UV_TOOL_DIR` can point to its `uv-runtime/tools` sibling for third-party uvx
   calls. Document disposable storage and automatic restoration on the next run. Keep reports
   in an explicit workspace outside the cache. Check the actual host's write access.
4. For ordinary execution use
   `uv run --locked --script "<script>"` with absolute paths outside
   the working directory. uv applies the script's metadata and lockfile, ignoring
   the consuming project's dependencies. uv automatically downloads missing packages
   and restores environments after cache cleanup. No separate sync is required.
   Report actual network or filesystem restrictions and use the host's normal
   permission mechanism. Add `--offline` only for deliberately offline execution
   with cached dependencies; it blocks uv's network access, not the script's. Update
   lockfiles explicitly when changing dependencies; never silently regenerate them
   during ordinary execution.
5. Disable bytecode in each entry point before local imports with
   `sys.dont_write_bytecode = True`. Python child processes reuse `sys.executable`
   and pass `-B` when executing another script. Disable pytest's cache provider
   or place its cache outside skill collections. Helpers imported by entry points
   do not need their own runtime metadata.
6. Keep uv's normal dependency isolation for third-party skills. Respect their
   declared dependencies and commands; the shared cache does not imply a shared
   environment. Explicit cache flags or changed environment variables can override
   user settings. A skill that creates its own project environment still needs
   separate review of that location. Avoid a global `UV_PROJECT_ENVIRONMENT`, custom
   environment launchers, readiness markers and path-hash caches.

## Verify before installation or packaging

- Exercise automatic installation on first run with an empty cache, then cached
  execution from source and installed
  copies, including a directory without a Python project and a project with
  conflicting dependencies. Confirm environments and caches stay outside the
  packages and the consuming project is unchanged.
- Check an empty cache with explicit `--offline`: the command must fail without
  downloading. Check stale script lockfiles: `--locked` must fail without rewriting
  them. Ordinary first-run installation must leave supplied lockfiles unchanged.
- Inspect hidden and Git-ignored package contents for generated state; git status
  alone does not prove package cleanliness. Bundle script lockfiles with scripts.
- Preserve existing user data when moving or cleaning runtime files. Record the
  commands, copies and runtime locations checked; report unavailable checks.
