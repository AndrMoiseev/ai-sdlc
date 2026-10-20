# Inspect — structural queries and maintenance

Use the invocation defined in [runtime setup](runtime-setup.md).

| Request | Command |
|---|---|
| Filter documents by metadata | `G query <conditions> --fields path,title,status,updated` |
| Count/group documents | `G query <conditions> --count-by service` |
| Knowledge-base quality/trust/staleness | `G health --json` |
| Ontology/link validation | `G lint [paths…] --strict --json` |
| Refresh search | `G index` |
| Existing index statistics | `G stat` |
| Bundled GitMark version | `G version` |

`query` reads frontmatter from Markdown without an index. Conditions are AND-ed:
`key=val`, `key!=val`, `key~substring`, `key>val`, `key<val`, `key?` (exists),
`!key` (missing). `status=draft|active` supplies alternatives. Quote conditions,
especially those containing shell operators. Nested fields include `generated.by`,
`verified.by`, `links.depends_on`; lists are expanded for matching/group counts.

Computed fields: `path`, `area`, `type` (alias for `node_type`),
`trust` (`unverified`, `machine`, `human`), `stale`. Dates compare lexically;
use consistent ISO dates. Query only includes docs with frontmatter, so counts
are not counts of every Markdown file. Missing fields affect negative conditions.
Inspect representative matching records before interpreting a complex count.

```text
G query "type=decision" "status=active" --fields path,title,updated
G query "type=plan" --count-by service
G query "generated.by?" "trust=unverified" --json
G query "updated<2026-01-01" "type=runbook"
G query "!description" --fields path,title
```

For lint/health interpretation, consult [Ontology](ontology.md). Use `--strict`
when testing lint's exit status: upstream's default reports errors but exits zero.
Warnings remain visible even with a successful strict run. Report errors and
warnings separately; resolve issues in the requested scope and identify pre-existing
issues outside it. A quality score is not proof of factual accuracy or human review.
