from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
from subprocess import CompletedProcess
import shutil
import pytest
import yaml


@pytest.fixture
def command_main(monkeypatch):
    """Exercise argument parsing, diagnostics and return codes without a child process."""
    scripts = Path(__file__).resolve().parents[2] / "sdd-shared/scripts"
    monkeypatch.syspath_prepend(str(scripts))

    def invoke(project, script="check.py", stage="documents", change="sample-change", work_kind="change"):
        main = runpy.run_path(str(scripts / script))["main"]
        args = ["--project-root", str(project), "--change", change,
                "--stage", stage, "--work-kind", work_kind]
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = main(args)
        return CompletedProcess(args, returncode, stdout.getvalue(), stderr.getvalue())

    return invoke


@pytest.fixture(scope="session")
def installed_packages(tmp_path_factory):
    """Share read-only installations; detect changed, missing and extra package files."""
    source = Path(__file__).resolve().parents[1]
    destination = tmp_path_factory.mktemp("installed skills")
    for name in ("sdd-spec", "sdd-shared"):
        shutil.copytree(source.parent / name, destination / name, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".venv", ".pytest_cache", ".cache"))

    def contents():
        return {path.relative_to(destination): path.read_bytes()
                for path in destination.rglob("*") if path.is_file()}

    before = contents()
    yield destination
    assert contents() == before, "Read-only installed packages changed during tests"


def write_doc(path, kind, records=(), **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(schema_version=1, document_type=kind, change_id="demo", language="en", **metadata)
    text = "---\n" + yaml.safe_dump(meta) + "---\n\n"
    for record in records:
        text += "### Record\n\n```yaml\n" + yaml.safe_dump(record, sort_keys=False) + "```\n\nDescription.\n\n"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "project with spaces"
    change = root / "sdd/changes/demo"
    records = [dict(sdd_record="requirement", id="REQ-feature", operation="add"), dict(sdd_record="acceptance", id="AC-feature", requirement="REQ-feature", conditions="Input", expected="Output")]
    task = dict(sdd_record="task", id="TASK-feature", number=1, covers=["AC-feature"], depends_on=[], status="pending", verification=[dict(criteria=["AC-feature"], test_description="Check output", location="tests/future.py", run=dict(command=["pytest", "tests/future.py"]))])
    write_doc(change / "proposal.md", "proposal")
    write_doc(change / "design.md", "design")
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    write_doc(change / "tasks.md", "tasks", [task])
    return root, change, deepcopy(records), deepcopy(task)

@pytest.fixture(autouse=True)
def checkpoint_observation(monkeypatch):
    """Git transitions are covered by shared adapter tests; vary observations here."""
    import lib.reviews as reviews
    observation = {"status": "ready", "head": "a" * 40, "accepted_commit": "a" * 40, "dirty": False}
    monkeypatch.setattr(reviews, "inspect", lambda *args: dict(observation))
    class EvidenceGit:
        def __init__(self, root):
            pass

        def commit_exists(self, oid):
            return oid not in observation.get("unavailable", [])
    monkeypatch.setattr(reviews, "Git", EvidenceGit)
    return observation
