"""Explicit execution ownership for verification records, independent of file names."""
KINDS = frozenset({"deterministic", "behavioral", "manual"})


def execution_kind(check):
    run = check.get("run", {})
    run = run if isinstance(run, dict) else {}
    kind = check.get("execution_kind", "deterministic" if "procedure" not in run else None)
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("execution_kind must be deterministic, behavioral or manual; procedures require an explicit type")
    return kind
