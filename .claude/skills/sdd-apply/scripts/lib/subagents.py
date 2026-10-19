"""Use the companion skill's resolver at the execution's original project root."""
from .inputs import spec_modules, basis_dependency


def resolver(state):
    return spec_modules(basis_dependency(state["basis"]), "subagents")


def resolve(state, kind, **kwargs):
    return resolver(state).resolve(project_root=state["basis"]["project_root"],
                                   role="sdd-apply." + kind, **kwargs)
