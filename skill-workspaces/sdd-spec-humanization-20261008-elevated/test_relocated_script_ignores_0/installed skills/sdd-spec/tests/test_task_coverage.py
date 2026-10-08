from copy import deepcopy
import pytest
from conftest import write_doc
from lib.validation import validate_documents


@pytest.mark.parametrize("count", [0, 2])
def test_exactly_one_owner(bundle, count):
    root, change, _, task = bundle
    tasks = [deepcopy(task) for _ in range(count)]
    if count == 2:
        tasks[1].update(id="TASK-other", number=2)
    write_doc(change / "tasks.md", "tasks", tasks)
    assert "task_coverage" in {e["code"] for e in validate_documents(root, change, "plan")["errors"]}


@pytest.mark.parametrize("covers", [["DEC-design"], ["other/AC-feature"], []])
def test_context_not_coverage(bundle, covers):
    root, change, _, task = bundle
    task["covers"] = covers
    write_doc(change / "tasks.md", "tasks", [task])
    assert validate_documents(root, change, "plan")["errors"]


def test_two_capabilities(bundle):
    root, change, records, task = bundle
    records[0]["id"] = "REQ-other"
    records[1].update(id="AC-other", requirement="REQ-other")
    write_doc(change / "specs/other/spec.md", "spec", records, capability="other")
    task["covers"].append("AC-other")
    task["verification"][0]["criteria"].append("AC-other")
    write_doc(change / "tasks.md", "tasks", [task])
    assert not validate_documents(root, change, "plan")["errors"]


def test_removal_still_needs_task(bundle):
    root, change, records, _ = bundle
    (root / "baseline.md").write_text("### Removed behavior\n")
    records[0].update(operation="remove", source=dict(kind="specification", path="baseline.md", requirement="Removed behavior"))
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    write_doc(change / "tasks.md", "tasks")
    assert "task_coverage" in {e["code"] for e in validate_documents(root, change, "plan")["errors"]}
