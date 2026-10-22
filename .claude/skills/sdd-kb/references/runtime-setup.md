# Runtime setup

Resolve the skill directory from the loaded `SKILL.md`, and the target repository
from the user's workspace. Use the repository root as the working directory;
never run against the skill directory itself. If no Git root exists, use the
explicit project directory. Check `uv --version`, `git --version`, and the bundled
`scripts/gitmark.py` and `scripts/gitmark.py.lock` before execution.
If any prerequisite is missing or its check fails, stop the selected route and
report the exact failing check and remedy. Resume after it succeeds; do not
continue with unverified runtime assumptions.

In every route, `G <arguments>` means this argument vector, not a shell variable:

```text
uv run --locked --script "<absolute-skill-dir>/scripts/gitmark.py" --root "<absolute-project-dir>" <arguments>
```

Resolve placeholders before execution. Pass queries and paths as individual quoted
arguments; never evaluate user input as shell code. Global `--root` precedes the
subcommand. `map -o` paths are relative to the working directory.

The script declares Python 3.10+, PyYAML and Markdown in PEP 723 metadata. Its
adjacent lockfile fixes the resolved versions. uv installs missing dependencies
and restores environments after cache cleanup; no project manifest, virtualenv
or `pip install` is needed. Use the normal command for first and subsequent runs.
Use `--offline` only when explicitly testing offline operation with cached packages.
Report actual missing tools, downloads or filesystem restrictions if a command fails.
Keep the shipped lockfile unchanged during ordinary use.

uv's user cache stores environments. On Windows, the once-per-user `UV_CACHE_DIR`
setting points to the absolute `uv-runtime/cache` directory under the system temp
directory; `UV_TOOL_DIR` may use its `uv-runtime/tools` sibling. Respect inherited
settings; do not change global configuration during a KB task. Temp storage is
disposable. Retain requested reports in the project or an explicit output directory.

GitMark writes `.gitmark/index.db` and, by default, `.gitmark/docs-map.html` inside
the target project. Keep `.gitmark/` out of version control; when authorized to edit
project configuration, add that entry to the existing `.gitignore` without replacing
it. Otherwise report the generated files. Skill packages/collections are rejected
as runtime output locations, including explicit `map -o` targets. Bytecode is disabled.

Discovery uses Git's tracked and untracked `.md` files minus `.gitignore`, built-in
exclusions, and root-relative prefixes in `.gitmarkignore` (one path per line).
Without Git, filesystem discovery applies built-in exclusions and `.gitmarkignore`,
but not `.gitignore`. This skill's own files and `.agents/`, `.claude/`, `.codex/`
are excluded. Add other vendored documentation or fixtures to `.gitmarkignore`
when they pollute search results. Search/map work on plain Markdown without ontology.

SQLite must include FTS5. Missing FTS5 produces an actionable error; an unavailable
trigram tokenizer disables that search channel. `index` always rebuilds the index;
`--force` is a compatibility flag. After edits/deletions, rebuild before searching.
`query`, `lint`, `health` and `map` read Markdown directly. `stat` describes the
existing index and cannot prove it is fresh.
