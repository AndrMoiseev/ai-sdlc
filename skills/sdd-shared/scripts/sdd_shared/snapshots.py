"""Read-only byte manifests for the normative inputs to a review."""
from hashlib import sha256
from pathlib import Path

from .paths import change_root, contained
from .documents import InputError, ValidationError


def snapshot(project_root: Path, change_id: str, stage: str) -> list[dict]:
    if stage not in {"documents", "plan"}:
        raise ValidationError("stage", "stage must be documents or plan")
    root = change_root(Path(project_root), change_id)
    paths = ["proposal.md", "design.md"]
    specs = contained(root, "specs")
    if not specs.is_dir():
        raise ValidationError("missing_specs", "Missing specs directory")
    paths.extend(p.relative_to(root).as_posix() for p in specs.rglob("spec.md"))
    if len(paths) == 2:
        raise ValidationError("missing_specs", "At least one capability spec is required")
    if stage == "plan":
        paths.append("tasks.md")
    manifest = []
    for relative in sorted(paths):
        path = contained(root, relative)
        try:
            digest = sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise InputError("unreadable_input", f"Cannot read {path}: {exc}") from exc
        manifest.append({"path": relative, "sha256": digest})
    return manifest

