import pytest
"""Reused preparation must preserve real validation and per-test isolation."""
from lib.common import git
from lib.inputs import validate


def test_copied_basis_matches_fresh_validation(project, basis):
    assert basis == validate(project, "demo", basis["instruction"])


def test_project_and_basis_do_not_mutate_templates(project, basis, project_template, basis_template):
    original = (project_template / "check.py").read_bytes()
    original_head = git(project_template, "rev-parse", "HEAD")
    (project / "check.py").write_text("assert False\n")
    git(project, "add", "check.py")
    git(project, "commit", "-m", "test-local mutation")
    basis["tasks"][0]["verification"][0]["run"]["command"].append("local")

    assert (project_template / "check.py").read_bytes() == original
    assert git(project_template, "rev-parse", "HEAD") == original_head
    assert git(project, "rev-parse", "HEAD") != original_head
    assert basis_template["tasks"][0]["verification"][0]["run"]["command"][-1] == "check.py"
    assert not git(project_template, "status", "--porcelain")

pytestmark = pytest.mark.native_git
