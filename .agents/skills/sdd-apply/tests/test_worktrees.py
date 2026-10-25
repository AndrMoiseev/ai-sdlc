from lib.repository import repository

from pathlib import Path
import pytest
from conftest import Driver



def test_task_branch_preserved_without_changing_main(basis, tmp_path):
    d = Driver(basis, parallel=True)
    result = d.send("worktree_create", {"workspace": str(tmp_path / "trees"), "resources": ["db-task-one"]})
    assert repository(result["path"]).head() == basis["head"]
    assert repository(result["path"]).branch() == result["branch"]
    assert result["branch"].startswith("sdd/")
    assert repository(basis["project_root"]).head() == basis["head"]
    (Path(result["path"]) / "unfinished").write_text("preserve")
    with pytest.raises(ValueError, match="unaccepted"):
        d.send("worktree_remove")
    assert (Path(result["path"]) / "unfinished").read_text() == "preserve"


def test_sequential_also_uses_isolated_worktree(driver, tmp_path):
    result = driver.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    assert driver.state["mode"] == "sequential"
    assert repository(result["path"]).branch() == result["branch"]
