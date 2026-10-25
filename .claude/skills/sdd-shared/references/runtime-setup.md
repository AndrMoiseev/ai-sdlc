# Runtime and installation

Install and update the aisdlc-core bundle as one unit. It supplies sdd-shared,
sdd-setup, sdd-spec, sdd-apply and sdd-sync as sibling skill folders. Individual skills have
no dependency manifests or separate installation lifecycle. For manual deployment,
copy the bundle's folders together, preserving scripts, adjacent lockfiles,
references, schemas and api.json. The shared API check detects an incomplete or
mixed installation; repair it by reinstalling the matching bundle.

Resolve `<shared-root>` from the installed package. Consumers find a sibling
sdd-shared directory, or accept an explicit root (`--sdd-shared` for setup,
`sdd_shared` in apply requests). Compatibility commands in sdd-spec use the sibling.
Resolve reference paths against this same package, including for an explicit root.
Missing files or API versions other than integer 1 produce an actionable error;
install the matching bundle before continuing dependent work.

Check `uv --version`, `uv cache dir`, the selected script and adjacent `.py.lock`.
Run `uv run --locked --script "<shared-root>/scripts/<command>.py" ...` from any cwd.
Each entry point supplies PEP 723 dependencies and its lockfile. uv installs missing
dependencies into its external cache; no consumer Python project or sync is needed.
On Windows use the inherited user `UV_CACHE_DIR` at `uv-runtime/cache` in system
temporary storage, with `UV_TOOL_DIR` at the sibling `tools` for uvx. Check actual
write access. Cache cleanup is safe: the next ordinary run restores the environment.

Use `--offline` only for an explicitly offline run. Report actual network or access
errors through the host's normal permission mechanism. Update stale locks explicitly
with `uv lock --script` when changing dependencies. Ordinary runs never rewrite locks.
Entry points disable bytecode before local imports; child Python processes use `-B`.
Keep environments, caches and generated results outside source and installed skill
collections. Store retained reports in an explicit workspace outside the uv cache.

Before distribution, run tests from source and relocated installations, with unrelated
and conflicting consumer projects. Check first-run installation, cached execution,
empty-cache offline failure, stale locks and unchanged project/package bytes. Inspect
hidden and ignored contents as well as Git status. Run the shared suite via
`uv run --locked --script "<shared-root>/scripts/test.py" -q`.
