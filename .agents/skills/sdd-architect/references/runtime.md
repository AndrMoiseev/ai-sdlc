# Runtime and storage

Use `uv` and a system Python 3.11+; Git is needed only for history and revision
identity. JDK `jdeps` and `scc` are needed only for their selected collection
branches. detekt and JaCoCo tasks belong to the consuming project's build.
Missing a tool limits that branch; preserve the other available evidence.

Keep environments, caches, fixtures and reports outside the consuming project
and all skill collections. Preserve inherited `UV_CACHE_DIR` and `UV_TOOL_DIR`.
If absent, resolve the OS temporary directory through its API and set absolute
`uv-runtime/cache` and `uv-runtime/tools` paths for the current process. Create
them and check `uv cache dir` plus actual create/write/read/list access. Reapply
these variables and `PYTHONDONTWRITEBYTECODE=1` in new shells.

Find Python once: `uv python find --system --no-managed-python ">=3.11"`.
Use its absolute path in every run. Entry points have PEP 723 metadata and
adjacent lockfiles; no project environment or dependency setup is required.

```text
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" identity --config "<workspace>/collection.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" collect --config "<workspace>/collection.json" --output "<workspace>/snapshot-1"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" analyze --snapshot "<workspace>/snapshot-1/snapshot.json" --output "<workspace>/analysis-1.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" rank --snapshot "<workspace>/snapshot-1/snapshot.json" --recommendations "<workspace>/cards.json" --output "<workspace>/ranked-1.json" --markdown "<workspace>/report-1.md"
```

Resolve placeholders before execution. Existing output paths are rejected to
retain the prior snapshot. JSON is the complete result; the Markdown output is
a starting report in the user's language, with at most five ready cards.
Inspect gaps in successful JSON results: success does not mean every measurement exists.

The scripts use only the standard library. Cached and empty-cache execution
therefore require no package download, including deliberate `--offline` runs.
Keep `--locked`; update a lock only as an intentional dependency change.

On filesystem errors, report the first failing path. Probe access with the same
interpreter and launch method; use the host's normal approval mechanism when
needed. Preserve the sandbox and ACLs. Windows commands launched by the collector
are hidden and terminate their process tree on timeout. It does not run arbitrary
command strings from a report or configuration.

Developer validation: run `scripts/test.py` through the same `uv --python ...
--locked --script ...` command. The full sequential suite has a 120-second
wall-clock budget including launch and setup. Stop the whole process tree if it
exceeds that budget. Keep evaluation results outside the package.
