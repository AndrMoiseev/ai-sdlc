"""Arrange external developer actions against either repository implementation."""
from lib.repository import repository
from lib.git_repository import GitRepository
from pathlib import Path


def write_file(root, name, content):
    """Arrange a working-tree edit in the selected boundary, without staging it."""
    repo = repository(root)
    if getattr(repo, "working_files", None) is not None:
        mode = repo.working_files.get(name, (None, "100644"))[1]
        repo.working_files[name] = content, mode
    else:
        path = Path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def remove_file(root, name):
    repo = repository(root)
    if getattr(repo, "working_files", None) is not None:
        del repo.working_files[name]
    else:
        Path(root, name).unlink()


def read_file(root, name):
    repo = repository(root)
    if getattr(repo, "working_files", None) is not None:
        return repo.working_files[name][0]
    return Path(root, name).read_bytes()


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


def accept_checkpoint(root, work_kind="change"):
    """Arrange explicit synthetic consent separately from making a commit."""
    repo = repository(root)
    if isinstance(repo, GitRepository):
        from conftest import SPEC
        from shared_commands import spec_modules
        observed = spec_modules(SPEC, "checkpoints").inspect(root, work_kind, "demo")
        repo._run("update-ref", observed["checkpoint_ref"], observed["head"])
    else:
        repo.accepted_checkpoint = repo.head()


def accept_execution_source(driver):
    """Record synthetic user acceptance for an explicitly arranged external fix."""
    state = driver.state
    head = repository(state["basis"]["project_root"]).head()
    return driver.send("resume", {"host_trace": "synthetic fixture", "live_contexts": [
        role["context_id"] for role in state["roles"].values() if role["status"] == "active"],
        "resolutions": [{"reason": "execution_head_changed", "head": head, "evidence": "Inspected fixture source change",
                         "instruction": {"text": "Accept fixture source", "source": "synthetic-user"}}]}, task_id=None)


def set_mode(root, path, executable):
    repo = repository(root)
    if isinstance(repo, GitRepository):
        repo._run("update-index", "--chmod=" + ("+x" if executable else "-x"), path)
    else:
        repo.index[path] = (repo.index[path][0], "100755" if executable else "100644")
        if repo.working_files is not None and path in repo.working_files:
            repo.working_files[path] = (repo.working_files[path][0], repo.index[path][1])


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
