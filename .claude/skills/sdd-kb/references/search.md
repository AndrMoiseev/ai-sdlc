# Search — kb-search + /kb

Use the invocation defined in [runtime setup](runtime-setup.md).

1. Empty query: run `G stat` and show `sdd-kb search <topic>` and
   `sdd-kb query <conditions>`. Stop without inventing a question.
2. Questions about document properties, counts or trust use
   [Inspect](inspect.md), which reads frontmatter directly.
3. For text questions, run `G index` if the index is absent or freshness is
   unknown, then `G search "<terms>" -k 8`. Use `--json` for machine-readable hits.
4. Open the 1–2 most relevant returned files at the indicated lines. Answer from
   their contents with file/line citations; a snippet alone is not evidence for
   details beyond it. Distinguish documented claims from code-verified behavior.
5. If no relevant result appears, retry once or twice using an exact identifier,
   a synonym or the other language (ru/en). Then state the documentation gap.

Results are one per file, best section first. Ranking fuses section terms,
title/description/tags/path, exact substrings and fuzzy matches. Search is lexical:
it tolerates forms and typos but cannot infer arbitrary synonyms. `[via]` identifies
matching channels; `stale`, deprecated/archived status and human verification are
signals to mention when they affect the answer. Prefer live verified documentation
when sources conflict, and make the conflict explicit.

Examples:

```text
G search "billing webhook signature" --type reference,runbook --status active
G search "лимит запросов" --service api --scope live --json
G search "migration" --scope history
```

`--scope live` excludes historical plan/report snapshots; it does not mean
`status=active`. Add `--status active` when that is required.
