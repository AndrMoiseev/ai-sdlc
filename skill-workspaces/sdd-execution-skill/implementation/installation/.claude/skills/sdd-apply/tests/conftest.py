from pathlib import Path
import pytest
import yaml
import sys
from lib.common import digest, git

SPEC = Path(__file__).resolve().parents[2] / "sdd-spec"


def document(path, meta, records=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(meta) + "---\n" + "\n".join("### Record\n\n```yaml\n" + yaml.safe_dump(r) + "```\n\nDescription.\n" for r in records), encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    change = root / "sdd/changes/demo"
    meta = dict(schema_version=1, change_id="demo", language="en")
    task = dict(sdd_record="task", id="TASK-one", number=1, covers=["AC-one"], depends_on=[], status="pending", verification=[dict(criteria=["AC-one"], test_description="Check result", location="check.py", run={"command": f'"{sys.executable}" -B check.py'})])
    for name in ("proposal", "design", "tasks"):
        document(change / (name + ".md"), {**meta, "document_type": name}, [task] if name == "tasks" else [])
    document(change / "specs/demo/spec.md", {**meta, "document_type": "spec", "capability": "demo"}, [dict(sdd_record="requirement", id="REQ-one", operation="add"), dict(sdd_record="acceptance", id="AC-one", requirement="REQ-one", conditions="Numbers", expected="Sum")])
    records = []
    for stage, kind in (("document_review", "document_approval"), ("plan_review", "plan_approval")):
        names = ["design.md", "proposal.md", "specs/demo/spec.md"] + (["tasks.md"] if stage == "plan_review" else [])
        manifest = [dict(path=n, sha256=digest((change / n).read_bytes())) for n in sorted(names)]
        for decision in (kind, "review_waiver"):
            records.append(dict(sdd_record="user", id="USER-" + stage.replace("_", "-") + "-" + decision.replace("_", "-"), kind=decision, scope={"stage": stage, **({"lenses": ["plan" if stage == "plan_review" else "consistency"]} if decision == "review_waiver" else {})}, response="Approved fixture", date="2026-10-08T00:00:00Z", inputs=manifest))
    document(change / "review/decisions.md", {"schema_version": 1}, records)
    document(change / "state.md", {**meta, "document_type": "state", "phase": "plan_approved", "awaiting": "none", "updated_at": "2026-10-08T00:00:00Z", "document_links": ["tasks.md"], "review_links": ["review/decisions.md"], "approval_refs": [r["id"] for r in records]})
    (root / "check.py").write_text("assert 2 + 3 == 5\n")
    git(root, "init")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture")
    return root


@pytest.fixture
def basis(project):
    from lib.inputs import validate
    return validate(project, "demo", {"text": "Implement plan", "source": "test-user-message"}, SPEC)


class Driver:
    """Synthetic host attestations for unit tests, never real-host evidence."""
    def __init__(self, basis, parallel=False):
        from lib.state import initialize
        self.directory = Path(basis["change_root"]) / "execution"
        initialize(basis, "owner", {"source": "test-message", "text": "parallel"} if parallel else None, parallel)
        # State-only tests do not exercise HTML; dashboard tests use the renderer.
        (self.directory / "dashboard.html").write_text("test-only dashboard sentinel")
        self.number = 0

    @property
    def state(self):
        from lib.state import read
        return read(self.directory)

    @property
    def task(self):
        return self.state["tasks"]["TASK-one"]

    def send(self, kind, payload=None, task_id="TASK-one"):
        from lib.state import apply
        self.number += 1
        state = self.state
        return apply(self.directory, {"event_id": f"event-{self.number}", "run_id": state["run_id"], "expected_revision": state["revision"], "owner": state["owner"], "type": kind, "task_id": task_id, "payload": payload or {}})

    def role(self, ident, kind, context=None):
        return self.send("role_register", {"role_id": ident, "kind": kind, "context_id": context or ident, "fresh": True, "host": "codex", "launch_ref": "synthetic-unit-test", "capabilities": {"fresh_context": True}})

    def start(self, paths=None):
        self.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
        self.role("author", "executor")
        self.send("start", {"role_id": "author", "paths": paths or ["result.txt", "check.py"]})
        self.send("check_run", {"role_id": "author", "stage": "baseline"})

    def freeze(self):
        self.send("role_result", {"role_id": "author", "result": "DONE", "trace": "unit-test"})
        self.send("candidate")

    def verify(self, role="verifier"):
        if role not in self.state["roles"]:
            self.role(role, "verifier")
        return self.send("check_run", {"role_id": role, "stage": "independent"})

    def review(self, role="reviewer", verdict="pass"):
        self.role(role, "reviewer")
        self.send("review_start", {"role_id": role})
        return self.send("review_result", {"role_id": role, "candidate": self.task["candidate"], "verdict": verdict, "findings": [], "test_integrity": "Assertions and skips inspected (unit fixture)", "trace": "unit-test"})


@pytest.fixture
def driver(basis):
    return Driver(basis)
