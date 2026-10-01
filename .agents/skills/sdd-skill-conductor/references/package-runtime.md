# Runtime state outside the skill package

Apply these requirements when creating a skill, changing its runtime commands,
or reviewing it for installation or packaging. They apply to any language and
dependency manager. Installers may copy entire directories, including files
ignored by Git; runtime state inside a skill can therefore become package content.

## Design and document the runtime

1. Keep source code, resources, dependency declarations and lockfiles in the
   package. Place dependency environments, caches, bytecode, logs and generated
   run results outside both source and installed skill directories, including
   the enclosing skill collections (such as `skills/`, `.agents/skills/` and
   `.claude/skills/`).
2. Configure external paths through a bundled launcher or tool configuration.
   Documented commands should work for source and installed copies without
   requiring users to set environment variables manually. Account for supported
   operating systems and isolate environments belonging to different copies.
3. Use the operating system's user cache directory for reconstructible
   environments and caches. Write reports and other retained outputs to an
   explicitly selected workspace outside the package. Document how users can
   locate these directories and rebuild the environment from its dependencies.
4. Skills without executable code need no launcher. Choose the smallest runtime
   mechanism that meets these requirements; keep it self-contained so the skill
   also works in repositories that do not contain the author's other skills.

## Verify before installation or packaging

- Run the applicable documented commands and inspect the package for generated
  state, including hidden and Git-ignored files. A clean `git status` alone does
  not establish a clean package.
- When changing the runtime mechanism, repeat the check from an installed copy
  and from a working directory outside the skill. Verify argument paths still
  resolve as documented and the external environment remains usable.
- Preserve existing user data before moving or cleaning generated files. Fix
  commands that leave runtime state inside the package before distributing it.
- Record which commands and copies were checked and where runtime state was
  written. If execution is unavailable, report the missing check explicitly.
