from lib.repository import repository

from pathlib import Path
import pytest
from conftest import Driver



def test_detached_preserved_and_no_branch(basis, tmp_path):
    d = Driver(basis, parallel=True)
    result = d.send("worktree_create", {"workspace": str(tmp_path / "trees"), "resources": ["db-task-one"]})
    assert repository(result["path"]).head() == basis["head"]
    assert repository(result["path"]).branch() is None
    (Path(result["path"]) / "unfinished").write_text("preserve")
    with pytest.raises(ValueError, match="unaccepted"):
        d.send("worktree_remove")
    assert (Path(result["path"]) / "unfinished").read_text() == "preserve"


def test_requires_parallel(driver, tmp_path):
    with pytest.raises(ValueError, match="parallel"):
        driver.send("worktree_create", {"workspace": str(tmp_path / "trees")})
