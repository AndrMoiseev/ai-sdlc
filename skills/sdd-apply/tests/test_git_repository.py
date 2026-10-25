"""Native-only semantics outside the intentionally small in-memory model."""
import pytest

from lib.repository import repository
from repository_support import stage, commit


pytestmark = pytest.mark.native_git


def test_filtered_content_and_raw_object_bytes_are_distinct(project):
    (project / ".gitattributes").write_bytes(b"windows.txt text eol=crlf\n")
    (project / "windows.txt").write_bytes(b"one\r\ntwo\r\n")
    stage(project, ".gitattributes", "windows.txt")
    sha = commit(project, "text filter")
    repo = repository(project)
    assert repo.content(sha, "windows.txt") == b"one\ntwo\n"
    assert repo.content(sha, "windows.txt", filtered=True) == b"one\r\ntwo\r\n"


def test_owned_commit_runs_hooks_without_replacing_the_foreign_index(project):
    repo = repository(project)
    (project / "result.txt").write_bytes(b"verified")
    (project / "foreign.txt").write_bytes(b"staged")
    stage(project, "foreign.txt")
    tree = repo.tree_for_paths(["result.txt"], repo.head())
    hook = project / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook changed' >> result.txt\n", encoding="utf-8")
    hook.chmod(0o755)
    sha = repo.commit_tree(tree, "owned commit with hook")
    assert (project / "result.txt").read_bytes() == b"verifiedhook changed"
    assert repo.content(sha, "result.txt") == b"verified"
    assert repo.content("", "foreign.txt") == b"staged"
