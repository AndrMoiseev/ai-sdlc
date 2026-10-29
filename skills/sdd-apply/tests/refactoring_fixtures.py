from repository_support import accept_checkpoint
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

def approved_basis(project, work_kind="refactoring", configure=None):
    """Both routes use the real document validator and synthetic approvals."""
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
        documents = {"proposal": [], "design": [result, preserved, decision], "tasks": [task, local, whole]}
        if configure:
            configure(documents)
        for name, records in documents.items():
            document(root / (name + ".md"), {**meta, "document_type": name}, records)
        approvals = []

        for stage, approval in (("documents", "document_approval"), ("plan", "plan_approval")):

            for kind in (approval, "review_waiver"):
                approvals.append(dict(sdd_record="user", id="USER-" + stage + "-" + kind.replace("_", "-"),
                                      work_kind=work_kind, change_id="demo", kind=kind,
                                      scope=dict(stage="document_review" if stage == "documents" else "plan_review",
                                                 **({"lenses": ["consistency" if stage == "documents" else "plan"]} if kind == "review_waiver" else {})),
                                      response="Approved synthetic test fixture", date="2026-10-24T00:00:00Z", basis_commit=repository(project).head()))
        document(root / "review/decisions.md", {**meta, "schema_version": 2, "document_type": "decisions"}, approvals)
        document(root / "state.yaml", {**meta, "document_type": "state", "phase": "plan_approved", "awaiting": "none",
                                    "updated_at": "2026-10-24T00:00:00Z", "document_links": ["tasks.md"],
                                    "review_links": ["review/decisions.md"], "approval_refs": [a["id"] for a in approvals]})
        stage_files(project, ".")
        commit(project, "Synthetic approved refactoring fixture")
        accept_checkpoint(project)
    return validate(project, "demo", {"text": "Execute the synthetic approved plan", "source": "synthetic-unit-test"},
                    work_kind=work_kind)


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
        return self.run_checks("baseline")

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
        result = self.run_checks("integration")
        if result["outcome"] == "passed":
            self.conclude(role="integration-verifier")
        return result

    def corrupt(self, mutate):
        """Inject a damaged persisted input, not an always-rejecting route stub."""
        state = deepcopy(self.state)
        mutate(state["tasks"]["TASK-one"])
        seal(state)
        save(self.directory, state)

    def log(self, result):
        return json.loads(artifacts.read_text(self.directory / result["log"]))


def transition_basis(project, revise_documents=None):
    """An approved temporary adapter followed by its removal and a test move."""
    def configure(documents):
        first, local, whole = documents["tasks"]
        first["scope"][0]["paths"] += ["adapter.py"]
        local.update(lifetime="transitional", until_task="TASK-two", replaced_by=["AC-removed"])
        second = deepcopy(first)
        second.update(id="TASK-two", number=2, depends_on=["TASK-one"],
                      scope=[dict(module="core", paths=["adapter.py", "check_removed.py", "check.py", "check_api.py"])],
                      test_changes=[dict(id="move-api-check", action="move", group="Arithmetic API regression in check.py",
                                         criteria=["AC-preserved"], replacement_criteria=["AC-preserved"],
                                         reason="Move the same arithmetic assertion after removing the adapter")])
        second["verification"][0].update(criteria=["AC-removed"], location="check_removed.py")
        second["verification"][0]["run"] = {"setup_required": "Create a check that the adapter is absent"}
        removed = dict(sdd_record="acceptance", id="AC-removed", task="TASK-two", lifetime="persistent",
                       conditions="The adapter is removed", expected="The arithmetic API remains available directly")
        later = deepcopy(second)
        later.update(id="TASK-three", number=3, depends_on=["TASK-two"],
                     scope=[dict(module="consumer", paths=["later.txt", "check_later.py"])], test_changes=[])
        later["verification"] = [dict(id="consumer", criteria=["AC-later"], test_description="Check the final consumer",
                                     location="check_later.py", run={"setup_required": "Create the consumer check"})]
        later["preserves"] = []
        later["preservation_reason"] = "The consumer task uses the confirmed mandatory API regression"
        local_later = dict(sdd_record="acceptance", id="AC-later", task="TASK-three", lifetime="persistent",
                           conditions="The consumer is ready", expected="The consumer uses the direct arithmetic API")
        documents["tasks"] = [first, local, second, removed, later, local_later, whole]
        whole.update(location="check_api.py", run={"command": [sys.executable, "-B", "check_api.py"]})
        if revise_documents:
            revise_documents(documents)
    return approved_basis(project, configure=configure)


class RegistryDriver(AcceptanceDriver):
    """Multi-task state operations, using synthetic native launches explicitly."""
    task_id = "TASK-one"

    @property
    def task(self):
        return deepcopy(self._view()["tasks"][self.task_id])

    @property
    def root(self):
        worktree = self._view()["tasks"][self.task_id]["worktree"]
        return Path(worktree["path"]) if worktree and not worktree.get("integrated") else Path(self._view()["basis"]["project_root"])

    def send(self, kind, payload=None, task_id="current"):
        return super().send(kind, payload, self.task_id if task_id == "current" else task_id)

    @property
    def author(self):
        return self.task_id + "-author"

    def start(self, additional=None):
        self.worktree()
        paths = self.task["plan"]["scope"][0]["paths"]
        self.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": additional or []})
        self.role(self.author, "executor")
        self.send("start", {"role_id": self.author, "paths": paths})
        verifier = self.task_id + "-baseline"
        self.role(verifier, "verifier")
        return self.run_checks("baseline")

    def implement(self):
        if self.task_id == "TASK-one":
            (self.root / "adapter.py").write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
            (self.root / "result.txt").write_text("adapter introduced\n", encoding="utf-8")
            name = "check_local.py"
            code = "from pathlib import Path\nnamespace = {}\nexec(Path('adapter.py').read_text(), namespace)\nassert namespace['add'](2, 3) == 5\n"
        elif self.task_id == "TASK-two":
            name = "check_removed.py"
            code = "from pathlib import Path\nassert not Path('adapter.py').exists()\nassert 2 + 3 == 5\n"
            (self.root / "adapter.py").unlink()
            (self.root / "check.py").rename(self.root / "check_api.py")
        else:
            name = "check_later.py"
            code = "from pathlib import Path\nassert Path('later.txt').read_text() == 'direct API consumer\\n'\n"
            (self.root / "later.txt").write_text("direct API consumer\n", encoding="utf-8")
        (self.root / name).write_text(code, encoding="utf-8")
        self.send("check_setup", {"check_id": self.task_id + ("/consumer" if self.task_id == "TASK-three" else "/local-result"),
                                 "command": [sys.executable, "-B", name], "description": "Verify this approved local result exactly"})

    def freeze(self):
        self.send("role_result", {"role_id": self.author, "result": "DONE", "trace": "synthetic-unit-test"})
        return self.send("candidate")

    def verify(self, role=None):
        return super().verify(role or self.task_id + "-verifier")

    def review(self, role=None, verdict="pass"):
        return super().review(role or self.task_id + "-reviewer", verdict)

    def resume(self):
        return self.send("resume", {"host_trace": "synthetic-unit-test liveness observation",
                                    "live_contexts": [role["context_id"] for role in self.state["roles"].values() if role["status"] == "active"]}, task_id=None)

    def revision(self):
        from lib.check_registry import selected
        before = deepcopy(selected(self.state, self.task))
        after = []
        for check in before:
            if check["id"] == "TASK-one/local-result":
                continue
            check = deepcopy(check)
            if check.get("location") == "check.py":
                check.update(location="check_api.py", run={"command": [sys.executable, "-B", "check_api.py"]})
            after.append(check)
        changed = {item["id"] for item in before if item not in after} | {item["id"] for item in after if item not in before}
        return dict(registry_revision=self.task["check_registry"]["revision"], before=before, after=after,
                    basis=dict(test_changes=["move-api-check"], transitional_criteria=["AC-local"]),
                    preserves=["AC-preserved"], reason="Approved adapter removal and preservation test move",
                    mapping={ident: "Temporary adapter criterion" if ident == "TASK-one/local-result" else "Arithmetic API regression in check.py moved intact to check_api.py" for ident in changed})


ATOMIC_OPERATION = """def transfer(accounts, amount):
    if amount < 0 or amount > accounts['left']:
        raise ValueError('invalid amount')
    accounts['left'] -= amount
    accounts['right'] += amount
"""
ATOMIC_CHECK = """from pathlib import Path
namespace = {}
exec(Path('ledger.py').read_text(), namespace)
accounts = {'left': 5, 'right': 2}
namespace['transfer'](accounts, 3)
assert accounts == {'left': 2, 'right': 5}
for amount in (-1, 9):
    before = dict(accounts)
    try:
        namespace['transfer'](accounts, amount)
    except ValueError as error:
        assert str(error) == 'invalid amount'
    else:
        raise AssertionError('invalid amount accepted')
    assert accounts == before
"""


def boundary_basis(project, split=False):
    """Persistent old structure, mixed atomicity test, then an approved new boundary."""
    def configure(documents):
        first, local, second, removed, later, local_later, whole = documents["tasks"]
        local.update(lifetime="persistent")
        local.pop("until_task")
        local.pop("replaced_by")
        second["scope"][0]["paths"] += ["ledger.py", "boundary.py", "check_contract.py", "check_local.py"]
        second["test_changes"] = [
            dict(id="retire-old-boundary", action="remove", group="adapter.py call asserted by check_local.py",
                 criteria=["AC-local"], reason="Merge the old modules", decision="DEC-local-boundary"),
            dict(id="move-api-check", action="adapt", group="check.py combines old adapter presence and atomic transfer",
                 criteria=["AC-preserved"], replacement_criteria=["AC-preserved"],
                 reason="Preserve atomicity at the public ledger boundary", decision="DEC-local-boundary"),
            dict(id="new-boundary", action="add", group="New boundary contract and ledger integration",
                 criteria=["AC-removed"], reason="Exercise invalid amounts across the extracted validator")]
        if split:
            second["verification"].append(dict(id="contract", criteria=["AC-removed"],
                test_description="Check extracted validation contract", location="check_contract.py",
                run={"setup_required": "Create the validator contract check"}))
        documents["tasks"] = [first, local, second, removed, whole]
        documents["design"][1].update(scope=["Public ledger"], conditions="Transfers succeed or reject invalid amounts",
            expected="Balances update together; invalid operations leave both balances unchanged")
        (project / "adapter.py").write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
        (project / "ledger.py").write_text(ATOMIC_OPERATION, encoding="utf-8")
        (project / "check.py").write_text(ATOMIC_CHECK + "assert Path('adapter.py').is_file()\n", encoding="utf-8")
    return transition_basis(project, revise_documents=configure)


class BoundaryDriver(RegistryDriver):
    def implement_boundary(self, split=False):
        super().implement()
        (self.root / "check_local.py").unlink()
        (self.root / "check_api.py").write_text(ATOMIC_CHECK, encoding="utf-8")
        if split:
            (self.root / "boundary.py").write_text(
                "def validate(balance, amount):\n    if amount < 0 or amount > balance:\n        raise ValueError('invalid amount')\n", encoding="utf-8")
            (self.root / "ledger.py").write_text(
                "from pathlib import Path\nvalidation = {}\nexec(Path('boundary.py').read_text(), validation)\n"
                "def transfer(accounts, amount):\n    validation['validate'](accounts['left'], amount)\n"
                "    accounts['left'] -= amount\n    accounts['right'] += amount\n", encoding="utf-8")
            (self.root / "check_contract.py").write_text(
                "from pathlib import Path\nnamespace = {}\nexec(Path('boundary.py').read_text(), namespace)\n"
                "assert namespace['validate'](5, 5) is None\n"
                "for amount in (-1, 6):\n    try:\n        namespace['validate'](5, amount)\n"
                "    except ValueError as error:\n        assert str(error) == 'invalid amount'\n"
                "    else:\n        raise AssertionError('invalid amount accepted')\n", encoding="utf-8")
            self.send("check_setup", {"check_id": "TASK-two/contract",
                "command": [sys.executable, "-B", "check_contract.py"], "description": "Validate the new boundary at both limits"})

    def revision(self):
        revision = super().revision()
        revision["basis"] = {"test_changes": ["retire-old-boundary", "move-api-check", "new-boundary"]}
        revision["reason"] = "DEC-local-boundary retires the old call; atomicity stays under AC-preserved"
        revision["mapping"]["TASK-one/local-result"] = "retire-old-boundary: check_local.py old call; DEC-local-boundary"
        for ident in revision["mapping"]:
            if ident != "TASK-one/local-result":
                revision["mapping"][ident] = "move-api-check: check.py old adapter assertion retired; check_api.py retains success, error and atomicity assertions; AC-preserved"
        return revision
