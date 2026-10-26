"""Reusable synthetic approved work and host events; never real user consent."""
from lib import artifact_storage as artifacts
from lib.repository import repository
from repository_support import stage as stage_files, commit
from copy import deepcopy
import json
from pathlib import Path
import sys

from conftest import Driver, document
from lib.inputs import spec_modules, validate
from lib.state import seal, save

COLLECTION = Path(__file__).resolve().parents[2]


def approved_basis(project, work_kind="refactoring"):
    """Both routes use the real document validator and synthetic approvals."""
    shared = COLLECTION / "sdd-shared"
    if work_kind == "refactoring":
        root = project / "sdd/refactoring/demo"
        meta = dict(schema_version=1, work_kind=work_kind, change_id="demo", language="en")
        local = dict(sdd_record="acceptance", id="AC-local", task="TASK-one", lifetime="persistent",
                     conditions="The local candidate is checked", expected="The local result is implemented")
        preserved = dict(sdd_record="criterion", id="AC-preserved", purpose="preservation", scope=["Arithmetic API"],
                         conditions="Existing clients add numbers", expected="Their sum is preserved",
                         source=dict(kind="specification", path="docs/baseline.md", requirement="Arithmetic contract"))
        result = dict(sdd_record="criterion", id="AC-result", purpose="result", scope=["Core and all consumers"],
                      conditions="The whole conversion is complete", expected="All consumers use the new boundary")
        decision = dict(sdd_record="decision", id="DEC-local-boundary", criteria=["AC-result", "AC-preserved"])
        local_check = dict(id="local-result", criteria=["AC-local"], test_description="Check local result",
                           location="check_local.py", run={"setup_required": "Create the local result check"})
        preservation_check = dict(id="api-regression", criteria=["AC-preserved"], test_description="Preserve arithmetic",
                                  location="check.py", run={"command": [sys.executable, "-B", "check.py"]})
        task = dict(sdd_record="task", id="TASK-one", number=1, scope=[dict(module="core", paths=["result.txt", "check_local.py", "check.py"])],
                    contributes_to=["AC-result"], preserves=["AC-preserved"], depends_on=[], status="pending",
                    verification=[local_check, preservation_check],
                    test_changes=[dict(id="add-local-check", action="add", group="Local core contract", criteria=["AC-local"], reason="Verify the new boundary")])
        whole = dict(sdd_record="verification", id="CHECK-whole", criteria=["AC-result", "AC-preserved"], test_description="Check every consumer and preserve the API",
                     location="check.py", run={"command": [sys.executable, "-B", "check.py"]})
        (project / "docs").mkdir(exist_ok=True)
        (project / "docs/baseline.md").write_text("# Arithmetic contract\nExisting clients receive their sum.\n", encoding="utf-8")
        for name, records in (("proposal", []), ("design", [result, preserved, decision]), ("tasks", [task, local, whole])):
            document(root / (name + ".md"), {**meta, "document_type": name}, records)
        approvals = []
        snapshots = spec_modules(shared, "snapshots")
        for stage, approval in (("documents", "document_approval"), ("plan", "plan_approval")):
            manifest = snapshots.snapshot(project, "demo", stage, work_kind)
            for kind in (approval, "review_waiver"):
                approvals.append(dict(sdd_record="user", id="USER-" + stage + "-" + kind.replace("_", "-"),
                                      work_kind=work_kind, change_id="demo", kind=kind,
                                      scope=dict(stage="document_review" if stage == "documents" else "plan_review",
                                                 **({"lenses": ["consistency" if stage == "documents" else "plan"]} if kind == "review_waiver" else {})),
                                      response="Approved synthetic test fixture", date="2026-10-24T00:00:00Z", inputs=manifest))
        document(root / "review/decisions.md", {**meta, "document_type": "decisions"}, approvals)
        document(root / "state.md", {**meta, "document_type": "state", "phase": "plan_approved", "awaiting": "none",
                                    "updated_at": "2026-10-24T00:00:00Z", "document_links": ["tasks.md"],
                                    "review_links": ["review/decisions.md"], "approval_refs": [a["id"] for a in approvals]})
        stage_files(project, ".")
        commit(project, "Synthetic approved refactoring fixture")
    return validate(project, "demo", {"text": "Execute the synthetic approved plan", "source": "synthetic-unit-test"},
                    sdd_shared=shared, work_kind=work_kind)


class AcceptanceDriver(Driver):
    """Actual reducer operations with explicitly synthetic native-role traces."""
    @property
    def root(self):
        state = self._view()
        worktree = state["tasks"]["TASK-one"]["worktree"]
        return Path(worktree["path"]) if worktree and not worktree.get("integrated") else Path(state["basis"]["project_root"])

    def start(self, paths=None, additional=None):
        self.worktree()
        self.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": additional or []})
        self.role("author", "executor")
        owned = ["result.txt", "check.py"]
        if self.state["basis"].get("work_kind") == "refactoring":
            owned.append("check_local.py")
        self.send("start", {"role_id": "author", "paths": paths or owned})
        self.role("baseline-verifier", "verifier")
        return self.send("check_run", {"role_id": "baseline-verifier", "stage": "baseline"})

    def implement(self):
        (self.root / "result.txt").write_text("local implemented\n", encoding="utf-8")
        if self.state["basis"].get("work_kind") == "refactoring":
            (self.root / "check_local.py").write_text("from pathlib import Path\nassert Path('result.txt').read_text() == 'local implemented\\n'\n", encoding="utf-8")
            self.send("check_setup", {"check_id": "TASK-one/local-result", "command": [sys.executable, "-B", "check_local.py"],
                                      "description": "Assert the exact local result; retain the existing API regression"})

    def integrate_verified(self):
        self.send("transfer")
        self.send("integrate")
        self.send("candidate")
        self.role("integration-verifier", "verifier")
        return self.send("check_run", {"role_id": "integration-verifier", "stage": "integration"})

    def corrupt(self, mutate):
        """Inject a damaged persisted input, not an always-rejecting route stub."""
        state = deepcopy(self.state)
        mutate(state["tasks"]["TASK-one"])
        seal(state)
        save(self.directory, state)

    def log(self, result):
        return json.loads(artifacts.read_text(self.directory / result["log"]))
