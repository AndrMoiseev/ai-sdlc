# Build — /onto-doc

Build or reconcile the KB for the requested scope. Empty `onto-doc`/`build` means
the whole repository; a named service, folder or document type narrows the scope.
Use [runtime setup](runtime-setup.md) and [Curate](curate.md).

1. Survey code, entry points, services/modules, build/deploy configuration and
   existing documentation. Run `G stat` and `G health --json`; distinguish an
   absent/stale index from an undocumented codebase. Record current coverage.
2. Form a concrete work list: service overviews, cross-cutting references,
   operational runbooks/gotchas, and decisions supported by evidence. Preserve
   existing documents and project layout. Bootstrap fills gaps; rebuilding
   reconciles current knowledge and does not mean deleting the existing KB.
3. If native subagents are available, dispatch independent areas in parallel.
   Give each curator the Curate and Ontology references, runtime invocation,
   source evidence, assigned paths and completion criteria. Tell workers they
   share the workspace, must preserve others' edits and own only their area.
   Keep shared `docs/README.md`, ontology vocabulary and entry-point edits under
   the coordinator. Run global lint/index/map only after workers finish, so
   concurrent processes do not rebuild the same SQLite file. Without subagents,
   process the same work list sequentially and report that execution mode.
4. Reconcile links, service vocabulary and indexes. Add a concise pointer to
   `docs/README.md` in an existing `AGENTS.md` or `CLAUDE.md`; preserve all existing
   instructions. If neither exists, create one minimal entry point, not two
   conflicting ones. Every documentation folder needs its README index.
5. Run `G lint --strict --json`; fix issues introduced by this build. Surface
   remaining problems explicitly. Run `G index`, `G health --json`, then
   `G map` (or the requested output path) and verify the HTML exists.
6. Report created/updated counts and paths, coverage before/after, lint errors
   and warnings, map path, and gaps requiring evidence or a human decision.

Finish when every planned area is covered or explicitly listed as unresolved,
the master index reaches the new docs, and derived artifacts reflect final files.
