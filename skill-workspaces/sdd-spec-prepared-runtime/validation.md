# Prepared runtime validation

Date: 2026-10-07. Host: Windows, Python 3.14.7, uv 0.12.5, APM 0.32.0.

## Scope and implementation

Updated the sdd-spec launcher, runtime instructions, package README and project
README. Added explicit setup with locked dependencies and optional development
dependencies. Ordinary commands use the prepared interpreter without uv, validate
dependency-file hashes, and disable bytecode writes. Tests use disposable system
temporary directories. Added the preparation/execution contract to the conductor's
package-runtime reference for future skills.

APM installation refreshed both managed copies and their deployment hashes.
Before installation, comparisons against both managed copies showed only the
intended changes. The execution-skill specification and its state were not edited.

## Evidence

- Source setup: `python skills/sdd-spec/scripts/run.py setup --dev`, exit 0.
  Existing dependencies were reused. This command used elevated execution to write
  the user cache.
- Source suite: `python skills/sdd-spec/scripts/run.py test -q`, 153 passed,
  1 skipped. Elevated execution was required for Windows temporary-directory access.
- Codex copy setup with `--dev`: exit 0. Full suite from this external working
  directory: 153 passed, 1 skipped, also with elevated filesystem access.
- Claude copy setup without `--dev`: exit 0; pytest and its dependencies were
  removed from that environment as expected for runtime-only preparation.
- `smoke.py` ran version, check and snapshot from a directory outside each package,
  against its own minimal fixture. All nine calls returned 0 in the sandbox with
  empty PATH and UV_OFFLINE=1. See `smoke-results.json`. The real change under
  sdd/changes/sdd-execution-skill was not used as a test fixture.
- Independent fresh-context reviewer `/root/review_prepared_runtime` identified
  a Windows case-sensitivity defect in collection-boundary checking. It was fixed
  with normcase and a regression case. Added failed setup, changed-input and missing
  interpreter coverage as well.
- Filesystem inspection of sdd-spec and sdd-skill-conductor in skills/, .agents/skills/
  and .claude/skills/ found no .venv, __pycache__, .pytest_cache, prepared.json or .pyc
  artifacts. Source/installed equality and changed deployment hashes were checked.
- All 188 installed files match their sources byte for byte. All 188 deployment
  hashes match LF-normalized content. Twenty-two unchanged installed files have
  CRLF working-tree bytes and therefore differ from the lockfile's raw hash;
  this change did not rewrite those files or their hashes.
- `git diff --check` reported no whitespace errors.

## Runtime locations and limits

Prepared environments remain in `%LOCALAPPDATA%/ai-sdlc/sdd-spec/<copy-id>/venv`,
with prepared.json beside each environment. The source, Codex and Claude copy IDs
in this workspace are 5c95f7fbb452f8f4, c547971f56e53ae1 and 6581cd13339c83fa.
The shared uv cache is under the same sdd-spec root, in uv/. Ordinary commands do
not invoke uv or write there. SDD_SPEC_RUNTIME_DIR optionally changes the root.

The initial full suite inside the Windows sandbox hit access errors on Python's
temporary directories (14 passed, 136 setup errors before later tests were added).
That is a remaining restriction for running pytest in this sandbox; the actual
check/snapshot commands passed there. Successful elevated suites do not establish
that pytest works in every sandbox. The failed run's temporary directory was removed.

POSIX paths were considered in implementation but not executed on Linux or macOS.
Dependency preparation was checked against existing environments; a fresh network
installation was not exercised. Instructions for other uv-based tools remain their
own responsibility; their launchers were not migrated in this change.
