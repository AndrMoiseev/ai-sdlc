# Curate — kb-curate + /doc

Use [runtime setup](runtime-setup.md) and the vocabulary in
[Ontology](ontology.md). The project `docs/ontology.md`, when present, supplies
project-specific vocabulary. Keep existing project conventions unless a migration
was requested. The bundled ontology is a reference, not a file to copy wholesale.

1. Find existing knowledge before writing: refresh the index if needed, run
   `G search "<topic>"`, and optionally `G query "type=<type>" --fields path,title`.
   Read related docs and the actual code/configuration. Update the existing document
   when the topic is already covered; don't create a duplicate.
2. Choose type and placement: service-specific → `docs/services/<service>/`,
   cross-cutting reference → `docs/reference/`, runbook/gotcha → `docs/ops/`,
   plan → `docs/plans/`, decision → `docs/decisions/`, report → `docs/reviews/`.
   A specification defaults to `reference`; a how-to to `guide`.
3. Write the document with `node_type`; for load-bearing docs include `title`,
   `description`, `service`, `status`, `updated`. Describe the question/symptom and
   key entities in one 12–30 word description, not a repetition of the title.
   Record observed facts and mark gaps explicitly. Do not invent a historical
   decision or rationale from code alone; record an inference or proposed decision
   as such, with draft status when appropriate.
4. Record authorship using the actual known tool/model and current UTC time:
   `generated: {by: <tool>/<model>, at: <ISO instant>}`. If the model is unknown,
   record the known tool only. Add `verified` only for an actual check and name
   that check truthfully; never self-assign `human:` verification. Material edits
   invalidate prior verification; remove stale entries. Use `stale_after` for
   perishable facts when there is a meaningful review deadline.
5. Add at least one typed link to existing code (`documents`, `implemented_by`)
   or related docs (`depends_on`, `relates_to`, `part_of`). Resolve paths from the
   document directory, or use `/path` for repository-relative links. Confirm targets
   exist. Add/update its parent README entry: `- [Title](file.md) — description`.
   Ensure new folders have README indexes and are reachable from `docs/README.md`.
6. Run `G lint <changed-doc-paths> --strict --json`, then full `G lint --strict --json`
   to catch inbound links and indexes. Fix introduced issues; report unrelated
   existing errors/warnings instead of rewriting the whole KB. Run `G index`.
   Optionally run `G health --json` for a quality snapshot.
7. Report created/updated paths, document types, added links and validation results.

For edits, bump `updated` when meaning changes and `generated.at` on substantial
agent rewrites. For deprecation, mark the old doc `deprecated` and add
`links.supersedes: [old.md]` on its replacement. For moves, use `git mv` for tracked
files (normal move for untracked files), fix both incoming and outgoing relative
links and both folder indexes. For requested deletions, check incoming links and
preserve knowledge still needed elsewhere; Git history alone does not justify deletion.

Before finishing: the facts have sources, link targets exist, README indexes include
the document, verification metadata is truthful, and the search index is current.
