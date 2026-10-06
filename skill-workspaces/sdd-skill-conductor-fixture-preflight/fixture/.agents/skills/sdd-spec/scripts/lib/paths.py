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


def change_root(project_root, change_id):
    if not valid_slug(change_id):
        raise ValidationError("invalid_change", "change_id must be lowercase-kebab-case, at most 64 characters")
    return contained(project_root, f"sdd/changes/{change_id}")
