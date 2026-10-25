"""Restore immutable source fixtures by bytes, without copying Git databases."""
import os
from pathlib import Path


def restore(root, files, directories):
    assert root.resolve() == root and not root.is_symlink()
    existing = {}
    def visit(directory, prefix=Path()):
        with os.scandir(directory) as entries:
            for entry in entries:
                assert not entry.is_symlink() and not (hasattr(entry, "is_junction") and entry.is_junction())
                relative = prefix / entry.name
                if entry.is_dir(follow_symlinks=False):
                    visit(entry.path, relative)
                    if relative not in directories:
                        os.rmdir(entry.path)
                elif relative not in files:
                    os.unlink(entry.path)
                else:
                    existing[relative] = entry.stat().st_mode
    if root.exists():
        visit(root)
    root.mkdir(parents=True, exist_ok=True)
    for relative in sorted(directories, key=lambda path: len(path.parts)):
        (root / relative).mkdir(exist_ok=True)
    for relative, (content, mode) in files.items():
        path = root / relative
        if relative not in existing or path.read_bytes() != content:
            path.write_bytes(content)
        if existing.get(relative) != mode:
            path.chmod(mode)


class WorkingCopies:
    def __init__(self, directory):
        self.directory = directory
        self.templates = {}

    def copy(self, template, repositories):
        if template not in self.templates:
            files, directories = {}, set()
            for path in template.rglob("*"):
                relative = path.relative_to(template)
                if ".git" in relative.parts:
                    continue
                assert not path.is_symlink()
                if path.is_dir():
                    directories.add(relative)
                else:
                    files[relative] = path.read_bytes(), path.stat().st_mode
            root = self.directory / str(len(self.templates)) / "project"
            self.templates[template] = root, files, directories
        root, files, directories = self.templates[template]
        restore(root, files, directories)
        repositories.seed(root, repositories.seeds[repositories(template).head()])
        return root
