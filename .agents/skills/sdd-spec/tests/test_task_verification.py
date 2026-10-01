import pytest
from conftest import write_doc
from lib.validation import validate_documents


@pytest.mark.parametrize("run", [dict(command="pytest"), dict(setup_required="Create test runner configuration within this task")])
def test_future_tests_and_run_setup(bundle, run):
    root, change, _, task = bundle
    task["verification"][0]["run"] = run
    write_doc(change / "tasks.md", "tasks", [task])
    assert not validate_documents(root, change, "plan")["errors"]


@pytest.mark.parametrize("mutation", [lambda c: c.update(criteria=[]), lambda c: c.update(test_description=""), lambda c: c.update(location=""), lambda c: c.update(run={}), lambda c: c.update(run=dict(command="pytest", procedure="docs.md")), lambda c: c.update(run=dict(procedure="missing.md")), lambda c: c.update(criteria=["AC-absent"]), lambda c: c.update(run=dict(setup_required=""))])
def test_invalid_verification(bundle, mutation):
    root, change, _, task = bundle
    mutation(task["verification"][0])
    write_doc(change / "tasks.md", "tasks", [task])
    assert validate_documents(root, change, "plan")["errors"]


def test_existing_procedure(bundle):
    root, change, _, task = bundle
    (root / "verification.md").write_text("Run smoke tests.\n")
    task["verification"][0]["run"] = dict(procedure="verification.md")
    write_doc(change / "tasks.md", "tasks", [task])
    assert not validate_documents(root, change, "plan")["errors"]
