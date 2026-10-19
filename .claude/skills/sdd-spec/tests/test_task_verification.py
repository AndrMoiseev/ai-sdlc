import pytest
from conftest import write_doc
from lib.validation import validate_documents


@pytest.mark.parametrize("run", [dict(command=["pytest"]), dict(command=["runner", "", "path with spaces", "&&"]), dict(setup_required="Create test runner configuration within this task")])
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


@pytest.mark.parametrize("command", ["pytest", "pytest && echo ok", [], [""], [" "], [42], ["pytest", None], ["pytest", "bad\0arg"], {"argv": ["pytest"]}])
def test_command_requires_argument_array(bundle, command):
    root, change, _, task = bundle
    task["verification"][0]["run"] = {"command": command}
    write_doc(change / "tasks.md", "tasks", [task])
    errors = validate_documents(root, change, "plan")["errors"]
    assert any(error["code"] == "verification_run" and "argument array" in error["message"] for error in errors)


@pytest.mark.parametrize("location", [
    "../outside.py", "/tests/test.py", "C:/tests/test.py", "tests\\test.py",
    "https://example.test/check", "tests/*.py", "tests/test.py::test_case",
    "docs/check.md#steps", ".", ".git/config", " tests/test.py", "tests/test.py\n",
    "tests/test.py; echo ok", "tests/[ab].py", "tests/test?.py",
])
def test_location_requires_project_path(bundle, location):
    root, change, _, task = bundle
    task["verification"][0]["location"] = location
    write_doc(change / "tasks.md", "tasks", [task])
    assert validate_documents(root, change, "plan")["errors"]


@pytest.mark.parametrize("kind", ["future", "file", "directory"])
def test_location_accepts_file_directory_and_future_path(bundle, kind):
    root, change, _, task = bundle
    location = root / "tests with spaces" / "verification"
    if kind == "file":
        location.parent.mkdir()
        location.write_text("assert True\n")
    elif kind == "directory":
        location.mkdir(parents=True)
    task["verification"][0].update(location="tests with spaces/verification", run={"setup_required": "Prepare and run checks"})
    write_doc(change / "tasks.md", "tasks", [task])
    assert not validate_documents(root, change, "plan")["errors"]
