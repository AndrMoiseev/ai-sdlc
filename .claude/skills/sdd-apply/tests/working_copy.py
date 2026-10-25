"""Restore immutable source fixtures by bytes, without copying Git databases."""


def restore(root, files, directories):
    assert root.resolve() == root and not root.is_symlink()
    for path in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        assert not path.is_symlink()
        relative = path.relative_to(root)
        if path.is_file() and relative not in files:
            path.unlink()
        elif path.is_dir() and relative not in directories:
            path.rmdir()
    root.mkdir(parents=True, exist_ok=True)
    for relative in sorted(directories, key=lambda path: len(path.parts)):
        (root / relative).mkdir(exist_ok=True)
    for relative, (content, mode) in files.items():
        path = root / relative
        if not path.is_file() or path.read_bytes() != content:
            path.write_bytes(content)
        if path.stat().st_mode != mode:
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
