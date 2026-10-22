# GitMark ontology

Adapted from Ontoship's `docs/ontology.md`; see [provenance](../UPSTREAM.md).
Markdown and Git are the source of truth. Each document is an object with a type,
frontmatter properties and links; the index and map are regenerated views.

## Document types

| `node_type` | Purpose | Default placement |
|---|---|---|
| `service` | Component overview | `docs/services/<service>/README.md` |
| `reference` | Cross-cutting specification | `docs/reference/` |
| `runbook` | Operational procedure | `docs/ops/` |
| `gotcha` | Pitfall and remedy | `docs/ops/` |
| `decision` | Recorded architectural/product choice | `docs/decisions/` |
| `plan` | Design before implementation | `docs/plans/` |
| `guide` | How-to or client guidance | Project-specific |
| `report` | Dated audit/analysis | `docs/reviews/` |
| `index` | Folder table of contents | `README.md` |

Load-bearing types are `service`, `reference`, `runbook`, `plan`, `decision`.
Use `reference` for a specification and `guide` for a how-to when uncertain.
Extend types only when none fits and there are at least three real examples.

## Frontmatter

`node_type` is required for load-bearing docs. Also supply `title`, `description`,
`service`, `status`, `updated`. Write the description as a useful search hook.
Optional `tags` and `aliases` improve lexical discovery.

Example for `docs/services/billing/README.md` (replace values with observed facts):

```yaml
---
node_type: service
title: Billing
description: "How billing accepts signed payment webhooks, rejects expired signatures and records payment events for downstream consumers."
service: billing
status: active
updated: YYYY-MM-DD
tags: [payments, webhooks]
generated: {by: agent-tool/model, at: "<current UTC ISO instant>"}
links:
  documents: [/src/billing]
  depends_on: [../../reference/architecture.md]
---
```

`status` values: `active`, `draft`, `deprecated`, `archived`; `stable` is accepted
for OKF-compatible documents. `type` is an alias for `node_type`; `index.md` is
accepted as an alternative folder index by the linter.

`generated: {by, at}` records authorship. `verified: [{by, at}, …]` records checks
actually performed. Actor forms include `<tool>/<model>`, `human:<id>` and
`process:<name>`. No verification means `unverified`; machine-only checks mean
`machine`; a real human entry means `human`. An agent cannot certify itself as
human-reviewed. Material changes invalidate old verification entries.

`stale_after` is an ISO instant for facts that need rechecking after a deadline.
Past that instant, lint reports I8 and search marks/demotes the document. `updated`
records meaningful content edits, not an automatic claim of correctness.

## Typed links

| Key under `links` | Meaning | Direction |
|---|---|---|
| `documents` | Describes code/component | doc → code |
| `implemented_by` | Implementation location | doc → source |
| `depends_on` | Prerequisite knowledge | doc → doc |
| `supersedes` | Replaces old knowledge | new → deprecated/archived doc |
| `relates_to` | Related topic | doc ↔ doc |
| `part_of` | Parent/index | doc → index |

Use lists of paths. Relative paths resolve from the document directory;
`/path` resolves from the repository root. Ordinary Markdown links imply
`relates_to`. Give each new doc a meaningful typed link and a parent index entry.
The HTML graph includes document links; code paths are validated but are not
rendered as documentation nodes.

## Project vocabulary and lint

Declare custom vocabulary in the target project's `docs/ontology.md` frontmatter:

```yaml
vocab:
  service: [api, billing, frontend]
  node_type: [meeting]
```

Without `vocab.service`, GitMark derives services from folders under `docs/` and
`services/`, `apps/`, `packages/`, `libs/`, `modules/`. Values starting with `_`
are cross-cutting sentinels such as `_platform`. Extension keys are `service`,
`node_type`, `status`, `link`; document deliberate additions rather than inventing
values on individual pages.

| Invariant | Check |
|---|---|
| I1 | Load-bearing document has typed frontmatter |
| I2 | Types, services, statuses and link types belong to vocabulary |
| I3 | Load-bearing document has incoming or outgoing links |
| I4 | Markdown targets exist |
| I5 | Documentation folders have README/index files |
| I6 | Superseded target is deprecated or archived |
| I7 | Typed links to code refer to existing paths |
| I8 | Staleness deadline has not passed |

Run `lint --strict --json` to distinguish errors, warnings and checked counts.
`health` reports coverage and metadata signals; neither command verifies prose
against running production systems. Ontology adoption is optional for search/map:
plain Markdown remains usable without retrofitting every existing file.
