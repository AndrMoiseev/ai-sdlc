"""Use the companion skill's resolver at the execution's original project root."""
from .inputs import spec_modules


def resolver(state):
    from pathlib import Path
    root = Path(state["basis"]["sdd_spec"])
    if not (root / "scripts/lib/subagents.py").is_file():
        raise ValueError("Update sdd-spec together with sdd-apply: shared subagent resolver is missing")
    module = spec_modules(root, "subagents")
    return module


def resolve(state, kind, **kwargs):
    return resolver(state).resolve(project_root=state["basis"]["project_root"],
                                   role="sdd-apply." + kind, **kwargs)
