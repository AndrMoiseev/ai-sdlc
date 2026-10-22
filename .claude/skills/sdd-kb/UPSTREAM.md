# Upstream provenance

- Source: [vakovalskii/ontoship](https://github.com/vakovalskii/ontoship)
- Revision: [`07eda61b4b15847371597937f6f620a2ae505720`](https://github.com/vakovalskii/ontoship/tree/07eda61b4b15847371597937f6f620a2ae505720)
- Retrieved: 2026-10-19
- License: MIT, original notice preserved in [LICENSE](LICENSE).
- Upstream CLI reports version `0.2.0`; this directory is an adapted distribution.

## Included sources

| Upstream path | Local destination |
|---|---|
| `skills/kb-search/SKILL.md` | `references/search.md`, `references/inspect.md`, `references/runtime-setup.md` |
| `skills/kb-curate/SKILL.md` | `references/curate.md`, `references/ontology.md` |
| `skills/kb-search/gitmark.py` | `scripts/gitmark.py` |
| `commands/kb.md` | Search/Inspect routes |
| `commands/kb-map.md` | Map route |
| `commands/doc.md` | Curate route |
| `commands/onto-doc.md` | Build route |
| `docs/ontology.md` | `references/ontology.md` |
| `LICENSE` | `LICENSE` |

The upstream regression suite is retained outside the installed skill at
`scripts/tests/sdd-kb/test_gitmark.py` in this repository, with adaptation tests.
`upstream-manifest.json` records the downloaded source hashes for future comparison.

## Deliberate changes

- One discoverable `SKILL.md` router; source skills and commands become internal
  references. No plugin registration, Claude-only variables, tool allowlists or
  separately installed slash commands are required.
- `dev-flow` and its `/ship` wrapper are excluded, including their instructions.
  Marketplace metadata, project-specific docs, benchmarks and media are not bundled.
- Add portable uv metadata and a lockfile with PyYAML/Markdown, disable bytecode,
  enforce external runtime output and explicit `shell=False` for Git subprocesses.
- Put the default HTML in `.gitmark/docs-map.html`. Serve that output directory
  on loopback; support an explicit directory for custom HTML output.
- Exclude this package and common agent installation directories from discovery;
  validate missing project paths, give an empty-map error and support UTF-8 output
  on Windows. Prefer `AGENTS.md` as a graph entry point when present.
- Fail visibly on unreadable Markdown, preserving the previous index on source
  read failure. Print an existing map URL or directory listing URL for custom output.
- Preserve project conventions, coordinate shared writes during bulk curation,
  support sequential execution when subagents are unavailable, and report
  unrelated existing lint errors instead of silently changing scope.
- Preserve truthfulness of authorship and verification across agent hosts.

To update, compare the pinned source files against a new upstream revision,
reapply these adaptations, refresh the manifest and run the regression/runtime
checks before replacing the revision. Do not overwrite adapted files blindly.
