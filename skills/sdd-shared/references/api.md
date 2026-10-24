# Shared API v1

`api.json` declares the package API version, independently of document
`schema_version`. Consumers require integer API version 1 and reject missing,
incomplete or incompatible packages before operating on project data.
This is an internal contract of aisdlc-core, not a per-skill dependency declaration.
Install and update the entire bundle; its skill folders use the shared sibling.

The public commands are `scripts/check.py`, `scripts/snapshot.py` and
`scripts/resolve_agent.py`. Run them with `uv run --locked --script` and absolute
paths; `--help` lists their arguments. Check/snapshot accept `--project-root`,
`--change` and `--stage documents|plan`. Resolve accepts the role, host and observed
parent model described in [subagent selection](subagents.md).

| Interface | Contract |
|---|---|
| `check.py` | JSON document, discussion, review and approval diagnostics; exits 0 for valid structure, 1 for structural errors, 2 for an unperformed check |
| `snapshot.py` | Sorted list of relative paths and SHA-256 hashes of original document bytes; exits 0/1/2 as before |
| `resolve_agent.py` | `{ok, result}` or error JSON; resolves selection without launching or writing settings |
| `sdd_shared.module(name)` | Imports one public domain module, leaving unrelated dependencies unloaded |
| `subagents` | `ROLES`, `settings`, `resolve`, `validate_selection`, `launch_identity`, strict JSON reads |
| `documents` | Document parsing, record IDs, `InputError` and `ValidationError` |
| `paths` | Contained document paths, change roots and verification locations |
| `validation`, `reviews`, `snapshots` | Structural validation, review/approval status and byte manifests |

The normative data formats are [document formats](document-format.md) and
[settings](subagents.md). `schemas/settings.schema.json` describes settings v1;
the Python reader additionally rejects duplicate keys and whitespace-only agent
names. Cross-record and filesystem constraints are checked by the Python modules.
Execution events and state remain owned by sdd-apply.

## Compatibility

The existing sdd-spec commands and `lib` imports delegate to this package. Their
CLI arguments, JSON shapes, exit codes and hash calculations are preserved.
New setup inspections and execution bases record `sdd_shared`. The old `sdd_spec`
argument and saved execution field locate sdd-shared alongside that former package;
the sdd-spec directory itself is not required. An explicit shared root takes
precedence for saved executions; conflicting explicit request arguments are rejected.
No fallback loads an old private implementation or an unrelated global installation.

Existing execution state is read without rewriting it or its integrity hash.
Install sdd-shared alongside its recorded sdd-spec location before resuming. A revised
approved plan records the shared root in the new basis. Old setup inspections/plans
must be inspected again after an upgrade because their dependency evidence changed;
the existing stale-plan check prevents writes and preserves the old plan.

The small `scripts/shared.py` bootstrap is shipped in each consumer because a
missing dependency cannot locate itself. Its copies must stay identical. It performs
discovery and API checks only; domain rules stay here.

## Refactoring document model

`api.json.work_kinds` advertises `change` and `refactoring`;
`document_schemas` lists supported versions for each kind/type pair. Both kinds
start with version 1. This adds capabilities to API v1; it does not migrate stored
documents or change the meaning of ordinary `covers`.

`documents.read_document(path, work_kind="change")` selects the schema using the
explicit context, declared kind, document type and version. Refactoring requires
an explicit context and `work_kind: refactoring` in frontmatter. Known SDD directory
roots must match the selection. Missing kind retains the ordinary change contract.

`validation.validate_documents(project_root, work_root, stage, work_kind="change")`
validates either model. Refactoring reads proposal/design and, for plan, tasks;
it requires `sdd/refactoring/<change_id>` and no specs. The return shape preserves
errors/warnings and plan tasks/progress. These are structural facts, not evidence
of whole-work completion or runtime retirement of transitional checks.

Consumers call `shared.locate(..., work_kind="refactoring")` or
`shared.load(root, module, work_kind="refactoring")` before dependent operations.
A legacy package without advertised support remains usable for ordinary changes;
an explicit refactoring request fails with an installation diagnostic instead of
loading the change schema. Install the matching whole bundle to repair missing
support. The full model is in the
[refactoring format](document-format-refactoring.md) and its linked JSON schema.
Public CLI/root resolution remains a separate consumer operation.
