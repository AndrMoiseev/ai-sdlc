# Fixture preflight verification

The setup defect was an omitted dependency in a disposable project, despite an
available installed humanizer-ru in the authoring repository.

Implemented mandatory `--fixture-manifest` in conductor's run_task.py and the
same validation on every invocation. `--preflight-only` never calls a model.
The resource inventory is derived from runtime instructions and exercised flows;
automatic inference of dependencies mentioned only in prose is not claimed.

- Offline regression suite: 27 tests passed (0.201 seconds on final run).
- Existing smoke suite: 12/12 passed.
- Real fixture with sdd-spec but no humanizer: exit 1 before model execution;
  missing SKILL.md, references/patterns.md and scripts/lint.py named in
  missing-dependency/preflight.json.
- Same fixture after copying installed humanizer: exit 0;
  present-dependency/preflight.json.
- Complete relocated conductor copy, invoked outside its skill directory:
  exit 0; installed-preflight/preflight.json.
- No model calls in these checks. No runtime cache directories in source or
  installed skill collections, including disposable copies. uv cache was kept
  at this workspace's uv-cache, outside the fixture skill collection.

The reusable premortem run_behavior.py now copies humanizer and supplies the
required inventory. Historical evaluation outputs were not rewritten or rerun.
Existing invocations of run_task.py must add --fixture-manifest; the updated
runtime-setup.md documents the required format and deliberate missing-dependency cases.
