"""Arrange external developer actions against either repository implementation."""
from lib.repository import repository
from lib.git_repository import GitRepository


def stage(root, *paths):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        repo._run("add", "--", *paths)
    else:
        repo.stage(paths)


def commit(root, message):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        repo._run("commit", "-m", message)
        return repo.head()
    return repo.commit_staged(message)


def set_mode(root, path, executable):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        repo._run("update-index", "--chmod=" + ("+x" if executable else "-x"), path)
    else:
        repo.index[path] = (repo.index[path][0], "100755" if executable else "100644")


def file_mode(root, path):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        return repo._text("ls-files", "--stage", "--", path).split()[0]
    return repo.index[path][1]


def ignore(root, pattern):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        from pathlib import Path
        common = Path(repo._text("rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = repo.root / common
        with (common / "info/exclude").open("a") as stream:
            stream.write("\n" + pattern + "\n")
    else:
        repo.store["ignores"].append(pattern)
