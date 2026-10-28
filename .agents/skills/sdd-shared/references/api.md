# Shared API v2

`api.json` declares the package API version, independently of document
`schema_version`. Consumers require integer API version 2 and reject missing,
incomplete or incompatible packages before operating on project data.
This is an internal contract of aisdlc-core, not a per-skill dependency declaration.
Install and update the entire bundle; its skill folders use the shared sibling.

The public commands are `scripts/check.py`, `scripts/checkpoint.py` and
`scripts/resolve_agent.py`. Run them with `uv run --locked --script` and absolute
paths; `--help` lists their arguments. Check accepts `--project-root`,
`--change` and `--stage documents|plan`. Resolve accepts the role, host and observed
parent model described in [subagent selection](subagents.md).

| Interface | Contract |
|---|---|
| `check.py` | JSON document, discussion, review and approval diagnostics; exits 0 for valid structure, 1 for structural errors, 2 for an unperformed check |
| `checkpoint.py` | inspect/accept/create; Git checkpoint observation and guarded writes; JSON schema v2 |
| `snapshot.py` | Migration diagnostic directing callers to checkpoint inspect; no normative byte manifest |
| `resolve_agent.py` | `{ok, result}` or error JSON; resolves selection without launching or writing settings |
| `sdd_shared.module(name)` | Imports one public domain module, leaving unrelated dependencies unloaded |
| `subagents` | `ROLES`, `settings`, `resolve`, `validate_selection`, `launch_identity`, strict JSON reads |
| `documents` | Document parsing, record IDs, `InputError` and `ValidationError` |
| `paths` | Contained document paths, change roots and verification locations |
| `validation`, `reviews`, `checkpoints` | Structural validation, commit review/approval diagnostics and accepted Git checkpoints |

The normative data formats are [document formats](document-format.md) and
[settings](subagents.md). `schemas/settings.schema.json` describes settings v1;
the Python reader additionally rejects duplicate keys and whitespace-only agent
names. Cross-record and filesystem constraints are checked by the Python modules.
Execution events and state remain owned by sdd-apply.

## Compatibility

Install API v2 consumers together. State/review/decisions use schema_version 2;
proposal/spec/design/tasks/questions/summary and lens index retain version 1.
Schema selection uses both work_kind and document_type. Check/checkpoint JSON
uses schema_version 2. Legacy normative manifests are migration evidence only.
A v1 current package requires migration_required and explicit acceptance of clean
HEAD before a separately authorized migration. Preserve reports without a proven
reviewed OID as legacy evidence outside the active v2 report set.

Apply execution basis uses plan_commit and document_paths instead of the normative
basis.manifest. Its persisted format requires explicit migration; independent
candidate, check registry and transfer integrity checks retain their own hashes.
The old sdd_spec locator can still locate its sibling sdd-shared; it does not permit
loading API v1. Refresh obsolete setup dependency evidence after the upgrade.

The small `scripts/shared.py` bootstrap is shipped in each consumer because a
missing dependency cannot locate itself. Its copies must stay identical. It performs
discovery and API checks only; domain rules stay here.

## Refactoring document model

`api.json.work_kinds` advertises `change` and `refactoring`;
`document_schemas` lists supported versions for each kind/type pair. Version selection is per kind and document type as listed above; ordinary covers retains its meaning.

`documents.read_document(path, work_kind="change")` selects the schema using the
explicit context, declared kind, document type and version. Refactoring requires
an explicit context and `work_kind: refactoring` in frontmatter. Known SDD directory
roots must match the selection. For unchanged v1 document types, missing kind retains the ordinary change contract. V2 state/review/decisions require explicit identity.

`validation.validate_documents(project_root, work_root, stage, work_kind="change")`
validates either model. Refactoring reads proposal/design and, for plan, tasks;
it requires `sdd/refactoring/<change_id>` and no specs. The return shape preserves
errors/warnings and plan tasks/progress. These are structural facts, not evidence
of whole-work completion or runtime retirement of transitional checks.

Consumers call `shared.locate(..., work_kind="refactoring")` or
`shared.load(root, module, work_kind="refactoring")` before dependent operations.
An incompatible package fails before dependent operations. Install the matching whole bundle. The full model is in the
[refactoring format](document-format-refactoring.md) and its linked JSON schema.
`paths.change_root(project_root, change_id, work_kind="change")` resolves either
allowed root with containment checks, including existing linked parents.
`paths.list_work(project_root, change_id=None)` returns explicit kind, ID, root
and `has_plan` for both roots without selecting a first match.

Check accepts `--work-kind change|refactoring`, defaulting to change. The compatible sdd-spec wrapper forwards the same option. Review and approval checks bind kind and ID; equal commits do not transfer authority between identities.

`reviews.review_status(project_root, work_root, stage, work_kind="change")`
checks that the selected root and document identities agree. State, decisions and review v2 require explicit work_kind and change_id for both kinds. Questions and summary retain their v1 schemas.

Apply validate/initialize accept `work_kind`, defaulting to `change` for existing
calls. Explicit null requests discovery across both roots; ambiguity returns the
available identities. Refactoring bases separate executable `tasks`, local
`acceptance` and whole-work `verification`. Initialize stores the latter records
as ID-keyed mappings without declaring them confirmed. Initial dashboards show
pending tasks and local criteria; read verifies the selected execution root.

## Git checkpoint operations

Run `uv run --python "<python>" --locked --script "<shared-root>/scripts/checkpoint.py"`
with `inspect|accept|create --project-root "<repo>" --work-kind change|refactoring --change <id>`.
Resolve Python and external runtime storage by [runtime setup](runtime-setup.md).

The ref is `refs/sdd/checkpoints/<work_kind>/<change-id>/<worktree-key>`.
The key is SHA-256 of the canonical absolute worktree Git directory (realpath,
platform normcase, UTF-8); it identifies location, not document contents.
Use Git APIs, including compare-and-swap update-ref, rather than editing .git.
Clone/push do not automatically transfer this ref. Missing ref requires explicit
acceptance; a symbolic ref or a non-commit target is an error.

`inspect --review-changes` adds reviewed_changes with paths, tree and index_tree.
Review the complete repository diff and staged index before using that observation.
`accept` requires --expected-head OID, --expected-accepted OID|null and
--decision JSON_FILE with id, response, source, date, accepted_commit.
It accepts only clean, unchanged HEAD and writes no working files.
`create` takes the same expected flags plus --reviewed-changes JSON_FILE
(the nested observation only), --instruction JSON_FILE with text/source and available
USER IDs, and --message TEXT. Keep temporary JSON inputs outside project and skills.
The main agent attests actual user authority and reviewed content; scripts cannot
prove a user's authorship. Subagents do not create commits or update refs.

Results include operation, status, work_kind, change_id, checkpoint_ref, head,
accepted_commit, dirty, changes, diagnostics; writes also include previous_accepted,
created_commit and ref_updated. Inspect exit 0 means observation succeeded, even
when status is dirty or head_mismatch. Write exit 0 means completed/unchanged;
exit 1 means unmet transition condition; exit 2 means tool/check failure.
A no-change transition creates no empty commit. Hooks run normally.

Checkpoint creation requires HEAD still at the accepted point, exact reviewed
content and clean completion. Hook mutation, external HEAD changes or failed ref
CAS preserve data and report the actual partial result. A created but unaccepted
commit is recovered by inspect and a user's explicit acceptance of clean HEAD.
No blind retry, reset or automatic acceptance repairs a race.

check reports checkpoint_status separately from review_status, approval_status
and discussion_status. Changed historical review evidence is diagnostic; ordinary
continuation checks the accepted point and next transition, not all past documents.
State acceptance never substitutes for a planning or implementation instruction.
