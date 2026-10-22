---
name: sdd-kb
description: >-
  Search, curate and map a repository's Markdown knowledge base with GitMark.
  Use for "find where this is documented", "which decisions are active",
  "update the project docs", "build a knowledge base from this repo", or
  "show the documentation graph", even without the words "knowledge base".
  Supports sdd-kb and legacy kb, kb-map, doc, onto-doc requests.
  Not for feature implementation, shipping, general web research or unrelated prose.
---

# SDD KB

Choose the route from the request; read only its reference and the
[runtime setup](references/runtime-setup.md). Paths are relative to this skill.

| Intent / command after `sdd-kb` | Route |
|---|---|
| Find documentation, answer from docs; `search`, `kb`, `kb-search` | [Search](references/search.md) |
| Filter/count frontmatter; `query`; inspect quality/index; `health`, `lint`, `stat`, `index`, `version` | [Inspect](references/inspect.md) |
| Create/edit/move/deprecate a document; `doc`, `curate`, `kb-curate` | [Curate](references/curate.md) |
| Bootstrap/rebuild KB for a repo or area; `build`, `onto-doc` | [Build](references/build.md) |
| Visualize documentation; `map`, `kb-map`, `serve` | [Map](references/map.md) |

Accept legacy names with or without `/` as routing aliases, not installed commands.
Preserve the remaining text as arguments. Structural questions under `kb` use Inspect.
For multiple intents, run the needed routes in dependency order.
For an empty request, show `stat` and brief usage; clarify only genuinely ambiguous intent.
`dev-flow` and `ship` are excluded: explain the boundary without starting a release workflow.
