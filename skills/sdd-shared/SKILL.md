---
name: sdd-shared
description: Shared SDD document formats, validation scripts and subagent configuration contracts. Use when sdd-setup, sdd-spec, sdd-apply or sdd-sync needs these resources, or when explicitly inspecting the shared SDD API. Do not use for starting planning, project setup or implementation workflows.
---

# SDD Shared

Use this package as the common contract for SDD consumers. Read only the reference
needed by the calling operation; its workflow retains responsibility for user
decisions, review authorization and execution.

## Resources

1. Resolve the installed package and check API compatibility using the
   [runtime contract](references/runtime-setup.md).
2. Select the required interface in [API v1](references/api.md).
3. For document reads, load the [document format](references/document-format.md)
   and the operation-specific section it names. For agent launches, read
   [subagent selection](references/subagents.md). For worker coordination, read
   [coordination](references/coordination.md).

## Ownership

The package owns parsers, validators, snapshots, settings and role resolution.
Authoring flows and templates belong to sdd-spec, configuration writes to sdd-setup,
execution state and Git operations to sdd-apply, and baseline synchronization and
change archiving to sdd-sync. A successful structural check
reports evidence; the calling workflow determines whether it may proceed.
