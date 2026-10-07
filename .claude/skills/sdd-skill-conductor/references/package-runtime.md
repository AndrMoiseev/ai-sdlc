# Runtime state outside the skill package

Apply these requirements when creating a skill, changing runtime commands,
or reviewing it for installation or packaging. Installers can copy entire
skill directories, including files ignored by Git.

## Design and document the runtime

1. Keep source code, resources and dependency declarations in the package.
   Keep environments, caches, bytecode and generated results outside source
   and installed skill collections, including skills/, .agents/skills/ and
   .claude/skills/.
2. Prefer one environment and lockfile in the consuming project. Source and
   installed copies use that environment; the script path does not select
   a separate environment. Resolve compatible dependencies together and
   document how a consumer connects the package to its project.
3. For uv projects, use the root .venv/ and configure cache-dir in the root
   uv.toml to .cache/uv. Ignore both runtime directories in Git. They must
   be writable in the agent's sandbox. Keep retained reports in an explicit
   workspace outside disposable caches.
4. Require uv as the entry point for Python scripts in authored skills.
   Prepare dependencies in a user terminal with network access using
   `uv sync --locked`. Document and use
   `uv run --directory <repo> --locked --offline python -B <script>`.
   Use absolute paths outside the project root. uv can synchronize packages
   from local cache; offline mode blocks uv's network access, not the script's.
   If packages are unavailable, report the failure and preparation command.
   If the lockfile is stale, update it explicitly as part of the dependency change.
   Python child processes reuse the interpreter selected by uv via sys.executable.
5. Let uv manage environments and dependency freshness. Avoid custom readiness
   markers, per-copy path hashes and launchers that duplicate dependency-manager
   behavior. A package can declare its dependencies without maintaining a second
   environment or lockfile. Scripts without Python dependencies need no uv project
   of their own.
6. Disable bytecode writes with Python -B. Route pytest caches and other generated
   output outside skill collections. Document the complete commands for preparing
   and running a standalone installed copy in another project as well.

## Verify before installation or packaging

- Exercise documented preparation and offline execution from source and installed
  copies, including an unrelated working directory. Confirm the interpreter belongs
  to the common environment and caches stay outside the packages.
- Check missing local dependencies and stale lockfiles: the command must fail
  without downloading or silently changing the lockfile.
- Inspect hidden and Git-ignored package contents for generated state; git status
  alone does not prove package cleanliness.
- Preserve existing user data when moving or cleaning runtime files. Record the
  commands, copies and runtime locations checked; report unavailable checks.
