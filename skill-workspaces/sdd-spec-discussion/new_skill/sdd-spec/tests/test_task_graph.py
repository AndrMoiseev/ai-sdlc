from copy import deepcopy
import pytest
from conftest import write_doc
from lib.validation import validate_documents


@pytest.mark.parametrize("dependency", ["TASK-absent", "other/TASK-feature", "TASK-feature", 1])
def test_invalid_dependency(bundle, dependency):
    root, change, _, task = bundle
    task["depends_on"] = [dependency]
    write_doc(change / "tasks.md", "tasks", [task])
    assert validate_documents(root, change, "plan")["errors"]


@pytest.mark.parametrize("number", [0, 2, True, "1"])
def test_numbers(bundle, number):
    root, change, _, task = bundle
    task["number"] = number
    write_doc(change / "tasks.md", "tasks", [task])
    assert "task_numbers" in {e["code"] for e in validate_documents(root, change, "plan")["errors"]}


def test_reorder_progress_conflicts_and_cycle(bundle):
    root, change, records, task = bundle
    records.append(dict(sdd_record="acceptance", id="AC-other", requirement="REQ-feature", conditions="Other", expected="Result"))
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    other = deepcopy(task)
    other.update(id="TASK-other", number=1, covers=["AC-other"], depends_on=["TASK-feature"])
    other["verification"][0]["criteria"] = ["AC-other"]
    task.update(number=2, status="done", cannot_parallel_with=["TASK-other"])
    write_doc(change / "tasks.md", "tasks", [task, other])
    result = validate_documents(root, change, "plan")
    assert not result["errors"]
    assert result["progress"] == dict(done=1, total=2)
    assert result["tasks"]["available_by_graph"] == ["TASK-other"]
    assert result["tasks"]["cannot_parallel_with"]["TASK-other"] == ["TASK-feature"]
    task["depends_on"] = ["TASK-other"]
    write_doc(change / "tasks.md", "tasks", [task, other])
    assert "task_cycle" in {e["code"] for e in validate_documents(root, change, "plan")["errors"]}


@pytest.mark.parametrize("field", ["number", "status", "covers", "depends_on", "cannot_parallel_with", "verification"])
@pytest.mark.parametrize("value", [None, {}, [[], {}]])
def test_malformed_task_field_returns_diagnostics(bundle, field, value):
    import json
    root, change, _, task = bundle
    task[field] = value
    write_doc(change / "tasks.md", "tasks", [task])
    result = validate_documents(root, change, "plan")
    assert result["errors"]
    json.dumps(result)
