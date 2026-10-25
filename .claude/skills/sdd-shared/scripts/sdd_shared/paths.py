"""Resolve only project-contained paths, including existing symlink parents."""
from pathlib import Path, PureWindowsPath
from .documents import ValidationError, valid_slug


def contained(root, relative, must_exist=False):
    root = Path(root).resolve()
    if not isinstance(relative, (str, Path)) or not str(relative):
        raise ValidationError("invalid_path", "Expected a nonempty relative path")
    raw = relative.as_posix() if isinstance(relative, Path) else relative
    rel = Path(raw)
    if rel.is_absolute() or PureWindowsPath(raw).drive or ":" in raw or "\\" in raw or ".." in rel.parts:
        raise ValidationError("path_escape", f"Path must stay under its root: {raw}")
    result = (root / rel).resolve()
    if not result.is_relative_to(root):
        raise ValidationError("path_escape", f"Path escapes its root: {raw}")
    if must_exist and not result.is_file():
        raise ValidationError("missing_path", f"Missing referenced file: {raw}")
    return result


WORK_ROOTS = {"change": "changes", "refactoring": "refactoring"}


def change_root(project_root, change_id, work_kind="change"):
    if not isinstance(work_kind, str) or work_kind not in WORK_ROOTS:
        raise ValidationError("unsupported_work_kind", "Expected change or refactoring")
    if not valid_slug(change_id):
        raise ValidationError("invalid_change", "change_id must be lowercase-kebab-case, at most 64 characters")
    return contained(project_root, f"sdd/{WORK_ROOTS[work_kind]}/{change_id}")


def list_work(project_root, change_id=None):
    """Return explicit route identities; discovery never selects the first match."""
    if change_id is not None and not valid_slug(change_id):
        raise ValidationError("invalid_change", "Invalid change_id")
    result = []
    for kind, directory in WORK_ROOTS.items():
        parent = contained(project_root, f"sdd/{directory}")
        if not parent.is_dir():
            continue
        for entry in sorted(parent.iterdir()):
            if not valid_slug(entry.name) or (change_id is not None and entry.name != change_id):
                continue
            root = change_root(project_root, entry.name, kind)
            if root.is_dir():
                result.append({"work_kind": kind, "change_id": entry.name,
                               "change_root": str(root), "has_plan": contained(root, "tasks.md").is_file()})
    return result


def verification_location(project_root, value):
    """Resolve a portable test/procedure location without requiring its creation."""
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(ord(c) < 32 or c in '*?[]#;|&<>`"' for c in value)):
        raise ValidationError("verification_location", "location must be one relative file/directory path without selectors, anchors or shell syntax")
    path = contained(project_root, value)
    root = Path(project_root).resolve()
    if path == root or ".git" in [part.lower() for part in path.relative_to(root).parts]:
        raise ValidationError("verification_location", "location must identify a file/directory below the project root, outside .git")
    return path
