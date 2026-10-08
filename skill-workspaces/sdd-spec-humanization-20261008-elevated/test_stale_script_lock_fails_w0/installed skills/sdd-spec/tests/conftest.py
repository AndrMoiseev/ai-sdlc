from copy import deepcopy
from pathlib import Path
import pytest
import yaml


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
    task = dict(sdd_record="task", id="TASK-feature", number=1, covers=["AC-feature"], depends_on=[], status="pending", verification=[dict(criteria=["AC-feature"], test_description="Check output", location="tests/future.py", run=dict(command="pytest tests/future.py"))])
    write_doc(change / "proposal.md", "proposal")
    write_doc(change / "design.md", "design")
    write_doc(change / "specs/feature/spec.md", "spec", records, capability="feature")
    write_doc(change / "tasks.md", "tasks", [task])
    return root, change, deepcopy(records), deepcopy(task)
