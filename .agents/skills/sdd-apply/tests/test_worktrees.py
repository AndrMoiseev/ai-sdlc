from pathlib import Path
import pytest
from conftest import Driver
from lib.common import git


def test_detached_preserved_and_no_branch(basis, tmp_path):
    d = Driver(basis, parallel=True)
    result = d.send("worktree_create", {"workspace": str(tmp_path / "trees"), "resources": ["db-task-one"]})
    assert git(result["path"], "rev-parse", "HEAD") == basis["head"]
    assert git(result["path"], "symbolic-ref", "-q", "HEAD", check=False) == ""
    (Path(result["path"]) / "unfinished").write_text("preserve")
    with pytest.raises(ValueError, match="unaccepted"):
        d.send("worktree_remove")
    assert (Path(result["path"]) / "unfinished").read_text() == "preserve"


def test_requires_parallel(driver, tmp_path):
    with pytest.raises(ValueError, match="parallel"):
        driver.send("worktree_create", {"workspace": str(tmp_path / "trees")})
