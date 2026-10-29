from pathlib import Path
from copy import deepcopy
import shutil
import pytest
import yaml
import sys
import json
import os
from lib.common import digest, git

@pytest.fixture(autouse=True)
def path_resolver(request, tmp_path_factory, monkeypatch):
    from lib.path_resolution import use_path_resolver
    native = any(request.node.get_closest_marker(mark) for mark in
                 ("native_paths", "native_git", "installation"))
    if native:
        yield
        return
    root = tmp_path_factory.getbasetemp().resolve()
    prefix = os.path.normcase(str(root)) + os.sep
    native_resolve = Path.resolve
    def no_links(path, strict=False):
        absolute = path if path.is_absolute() and ".." not in path.parts else Path(os.path.abspath(path))
        name = os.path.normcase(str(absolute))
        if name != prefix[:-1] and not name.startswith(prefix):
            return native_resolve(path, strict=strict)
        if name[len(prefix):].partition(os.sep)[0].endswith("current"):
            return native_resolve(path, strict=strict)
        if strict:
            absolute.stat()
        return absolute
    symlink = os.symlink
    def unsupported(source, destination, *args, **kwargs):
        destination = Path(os.path.abspath(destination))
        if destination.parent == root and destination.name.endswith("current"):
            return symlink(source, destination, *args, **kwargs)  # pytest's temporary-directory bookkeeping.
        pytest.fail("Filesystem-link tests require native_paths or native_git")
    monkeypatch.setattr(os, "symlink", unsupported)
    # Companion validators and fixture helpers also resolve temporary paths.
    # Apply the same no-links contract there; package paths still use the OS.
    monkeypatch.setattr(Path, "resolve", no_links)
    with use_path_resolver(no_links):
        yield


@pytest.fixture(scope="session")
def repository_seeds(project_template):
    from memory_repository import capture_seed
    seed = capture_seed(project_template)
    return {seed["head"]: seed}


@pytest.fixture(autouse=True)
def repository_backend(request, monkeypatch):
    from functools import lru_cache
    from lib.repository import use_repositories
    from lib.git_repository import GitRepository
    from memory_repository import MemoryRepositories
    native = request.node.get_closest_marker("native_git") or request.node.get_closest_marker("installation")
    seeds = request.getfixturevalue("repository_seeds") if not native and "project_template" in request.fixturenames else {}
    factory = lru_cache(None)(GitRepository) if native else MemoryRepositories(seeds)
    if not native:
        def unexpected(*args, **kwargs):
            pytest.fail("Native Git escaped the repository test interface; mark a Git contract test native_git")
        monkeypatch.setattr(GitRepository, "_run", unexpected)
    with use_repositories(factory):
        yield factory


@pytest.fixture(autouse=True)
def state_backend(request):
    from lib.artifact_storage import FileArtifacts, use_artifacts
    from lib.state_storage import FileStateStorage, use_storage
    from memory_state import MemoryStates
    native = any(request.node.get_closest_marker(mark) for mark in ("native_state", "installation"))
    factory = FileStateStorage if native else MemoryStates()
    artifacts = FileArtifacts() if native else factory.artifacts
    with use_storage(factory), use_artifacts(artifacts):
        yield factory


@pytest.fixture(autouse=True)
def check_runner(request, monkeypatch):
    if any(request.node.get_closest_marker(mark) for mark in ("native_process", "installation")):
        return
    from lib import verification
    from check_commands import run_command
    monkeypatch.setattr(verification.check_runner, "run_command", run_command)


@pytest.fixture
def prepare_state(request):
    """Build native-storage preconditions in memory; test the disk boundary itself."""
    from contextlib import contextmanager
    from lib.artifact_storage import use_artifacts
    from lib.state_storage import FileStateStorage, use_storage
    from memory_state import MemoryStates

    @contextmanager
    def prepare():
        if not request.node.get_closest_marker("native_state"):
            yield
            return
        states = MemoryStates()
        with use_storage(states), use_artifacts(states.artifacts):
            yield
        for directory in states.artifacts.directories:
            directory.mkdir(parents=True, exist_ok=True)
        for path, content in states.artifacts.files.items():
            path.write_bytes(content)
        for directory, store in states.stores.items():
            FileStateStorage(directory).replace(store.read())

    return prepare


@pytest.fixture(autouse=True)
def shared_cli(monkeypatch):
    from lib import inputs
    from shared_commands import spec_call, spec_modules
    original = inputs.spec_call
    monkeypatch.setattr(inputs, "spec_call", spec_call)
    monkeypatch.setattr(inputs, "spec_modules", spec_modules)
    return original


def document(path, meta, records=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    if meta.get("document_type") == "state":
        assert path.name == "state.yaml" and not records
        meta = dict(meta, schema_version=2, work_kind=meta.get("work_kind", "change"), flow="plan", next_question=None,
                    checks={"structure": "passed"})
        path.write_text(yaml.safe_dump(meta), encoding="utf-8")
        path.with_suffix(".md").write_text("# Continue the approved plan\n", encoding="utf-8")
        return
    path.write_text("---\n" + yaml.safe_dump(meta) + "---\n" + "\n".join("### Record\n\n```yaml\n" + yaml.safe_dump(r) + "```\n\nDescription.\n" for r in records), encoding="utf-8")


@pytest.fixture(scope="session")
def project_template(tmp_path_factory):
    """Build one immutable repository per worker; tests use independent copies."""
    root = tmp_path_factory.mktemp("project-template") / "project"
    change = root / "sdd/changes/demo"
    meta = dict(schema_version=1, change_id="demo", language="en")
    task = dict(sdd_record="task", id="TASK-one", number=1, covers=["AC-one"], depends_on=[], status="pending", verification=[dict(criteria=["AC-one"], test_description="Check result", location="check.py", run={"command": [sys.executable, "-B", "check.py"]})])
    for name in ("proposal", "design", "tasks"):
        document(change / (name + ".md"), {**meta, "document_type": name}, [task] if name == "tasks" else [])
    document(change / "specs/demo/spec.md", {**meta, "document_type": "spec", "capability": "demo"}, [dict(sdd_record="requirement", id="REQ-one", operation="add"), dict(sdd_record="acceptance", id="AC-one", requirement="REQ-one", conditions="Numbers", expected="Sum")])
    records = []
    for stage, kind in (("document_review", "document_approval"), ("plan_review", "plan_approval")):
        for decision in (kind, "review_waiver"):
            records.append(dict(sdd_record="user", id="USER-" + stage.replace("_", "-") + "-" + decision.replace("_", "-"), kind=decision, work_kind="change", change_id="demo", scope={"stage": stage, **({"lenses": ["plan" if stage == "plan_review" else "consistency"]} if decision == "review_waiver" else {})}, response="Approved fixture", date="2026-10-08T00:00:00Z", basis_commit="a" * 40))
    document(change / "review/decisions.md", {"schema_version": 2, "document_type": "decisions", "work_kind": "change", "change_id": "demo"}, records)
    document(change / "state.yaml", {**meta, "document_type": "state", "phase": "plan_approved", "awaiting": "none", "updated_at": "2026-10-08T00:00:00Z", "document_links": ["tasks.md"], "review_links": ["review/decisions.md"], "approval_refs": [r["id"] for r in records]})
    (root / "check.py").write_text("assert 2 + 3 == 5\n")
    # Contract tests install the hooks they exercise. Git's sample hooks and
    # default template files otherwise get copied into every native fixture.
    template = root.parent / "empty-git-template"
    template.mkdir()
    git(root, "init", "--template=" + str(template))
    (root / ".git/hooks").mkdir()
    (root / ".git/info").mkdir()
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture")
    from shared_commands import spec_modules
    checkpoints = spec_modules("checkpoints")
    observed = checkpoints.inspect(root, "change", "demo")
    git(root, "update-ref", observed["checkpoint_ref"], observed["head"])
    return root


def copy_project(template, destination, backend, omit=()):
    from memory_repository import MemoryRepositories
    if isinstance(backend, MemoryRepositories):
        root = shutil.copytree(template, destination, ignore=shutil.ignore_patterns(".git", *omit))
        backend.seed(root, backend.seeds[backend(template).head()])
        return root
    root = shutil.copytree(template, destination)
    from shared_commands import spec_modules
    observed = spec_modules("checkpoints").inspect(root, "change", "demo")
    git(root, "update-ref", observed["checkpoint_ref"], observed["head"])
    return root


@pytest.fixture
def project(tmp_path, project_template, repository_backend, working_copies):
    from memory_repository import MemoryRepositories
    if isinstance(repository_backend, MemoryRepositories):
        return working_copies.copy(project_template, repository_backend)
    return copy_project(project_template, tmp_path / "project", repository_backend)


@pytest.fixture(scope="session")
def working_copies(tmp_path_factory):
    from working_copy import WorkingCopies
    return WorkingCopies(tmp_path_factory.mktemp("working-copies"))


@pytest.fixture(scope="session")
def basis_template(project_template, repository_seeds):
    from unittest.mock import patch
    from lib.inputs import validate
    from shared_commands import spec_call
    from lib.repository import use_repositories
    from memory_repository import MemoryRepositories
    with use_repositories(MemoryRepositories(repository_seeds)), patch("lib.inputs.spec_call", spec_call):
        return validate(project_template, "demo", {"text": "Implement plan", "source": "test-user-message"})


@pytest.fixture
def basis(project, basis_template):
    # Only the two roots change when the byte-identical repository is copied.
    # Input-validation tests still call validate on their actual modified project.
    result = deepcopy(basis_template)
    result.update(project_root=str(project), change_root=str(project / "sdd/changes/demo"))
    return result


class Driver:
    """Synthetic host attestations for unit tests, never real-host evidence."""
    def __init__(self, basis):
        from lib.state import initialize
        self.directory = Path(basis["change_root"]) / "execution"
        self.directory.mkdir(parents=True, exist_ok=True)
        initialize(basis, isolation=True)
        # State-only tests do not exercise HTML; dashboard tests use the renderer.
        from lib.artifact_storage import write
        write(self.directory / "dashboard.html", "test-only dashboard sentinel")
        self.number = 0

    @property
    def state(self):
        view = self._view()
        return deepcopy(view)

    def _view(self):
        from lib.state import read
        from lib.state_storage import storage
        from memory_state import MemoryStateStorage
        store = storage(self.directory)
        if not isinstance(store, MemoryStateStorage):
            return read(self.directory)
        raw = store.read()
        if raw != getattr(self, "_state_bytes", None):
            self._state_view = read(self.directory)
            self._state_bytes = raw
        return self._state_view

    @property
    def task(self):
        # Preserve lazy object references in the independent view. Serializing
        # here eagerly reads the complete evidence/review history on every get.
        return deepcopy(self._view()["tasks"]["TASK-one"])

    @property
    def root(self):
        from lib.verification import root_for
        state = self._view()
        return Path(root_for(state, state["tasks"]["TASK-one"]))

    def worktree(self):
        if not self.task["worktree"]:
            project = Path(self.state["basis"]["project_root"])
            self.send("worktree_create", {"workspace": str(project.parent / "task-worktrees")})
        return self.root

    def send(self, kind, payload=None, task_id="TASK-one"):
        from lib.state import apply
        self.number += 1
        state = self._view()
        return apply(self.directory, {"event_id": f"event-{self.number}", "run_id": state["run_id"], "expected_revision": state["revision"], "type": kind, "task_id": task_id, "payload": payload or {}})

    def role(self, ident, kind, context=None):
        return self.send("role_register", {"role_id": ident, "kind": kind, "context_id": context or ident, "fresh": True, "host": "codex", "launch_ref": "synthetic-unit-test", "capabilities": {"fresh_context": True}})

    def explorer(self, ident, stage=None, task_id="current", context=None, **fields):
        from lib.explorer_assignments import basis
        selected_task = getattr(self, "task_id", "TASK-one") if task_id == "current" else task_id
        state = self._view()
        task = state["tasks"].get(selected_task)
        kind = "checks" if stage else "research"
        current = basis(state, task, kind, stage)
        assignment = {"id": ident, "kind": kind,
            "scope": {"project": state["basis"]["project_root"], "work": state["change_id"], "task": selected_task},
            "basis": current, "read_scope": ["project"], "outputs": [str(self.directory)], "limits": {"timeout": 300}}
        if stage:
            assignment.update(stage=stage, check_ids=[check["id"] for check in current["checks"]],
                              registry_revision=current["registry_revision"])
        else:
            assignment["question"] = "Inspect the synthetic fixture"
        payload = {"role_id": ident, "kind": "explorer", "context_id": context or ident, "fresh": True,
            "host": "codex", "launch_ref": "synthetic-unit-test", "assignment": assignment,
            "capabilities": {"fresh_context": True, "observations": {
                name: {"available": True, "trace": "synthetic adapter observation"}
                for name in ("launch", "read", "write_artifacts", "run_command")}}, **fields}
        return self.send("role_register", payload, task_id=selected_task)

    def run_checks(self, stage, ident=None, task_id="current"):
        ident = ident or f"{getattr(self, 'task_id', 'TASK-one')}-{stage}-explorer-{self.number + 1}"
        self.explorer(ident, stage, task_id=task_id)
        selected_task = getattr(self, "task_id", "TASK-one") if task_id == "current" else task_id
        result = self.send("check_run", {"role_id": ident, "stage": stage}, task_id=selected_task)
        self.send("role_result", {"role_id": ident, "result": "DONE", "trace": "synthetic adapter check completed"}, task_id=selected_task)
        return result

    def start(self, paths=None):
        self.worktree()
        self.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
        self.role("author", "executor")
        self.send("start", {"role_id": "author", "paths": paths or ["result.txt", "check.py"]})
        self.run_checks("baseline")

    def freeze(self):
        self.send("role_result", {"role_id": "author", "result": "DONE", "trace": "unit-test"})
        self.send("candidate")

    def verify(self, role="verifier"):
        if role not in self.state["roles"]:
            self.role(role, "verifier")
        result = self.run_checks("independent")
        if result["outcome"] == "passed":
            self.conclude(role=role)
        return result

    def conclude(self, role="verifier", stage=None, outcome="passed", check_request=None, task_id="current"):
        """Explicit synthetic criterion assessment, separate from the runner."""
        from lib.verification_results import packet
        selected_task = getattr(self, "task_id", "TASK-one") if task_id == "current" else task_id
        state = self._view()
        task = state["tasks"].get(selected_task)
        context = packet(state, task, self.directory, stage)
        criteria_results = [{"criterion_id": criterion, "outcome": outcome,
                             "reason": "Synthetic fixture criterion and test source inspected",
                             "references": ["synthetic fixture source and registered check"]}
                            for criterion in context.pop("criteria")]
        if check_request:
            for item in criteria_results:
                item["check_request"] = check_request
        if stage:
            context["stage"] = stage
        return self.send("verification_result", {**context, "role_id": role,
            "criteria_results": criteria_results, "limitations": [], "trace": "synthetic-unit-test conclusion"},
            task_id=selected_task)

    def final_conclude(self, task_id="current", outcome="passed"):
        """Separate synthetic final assessment; never inferred by production code."""
        selected_task = getattr(self, "task_id", "TASK-one") if task_id == "current" else task_id
        ident = f"final-verifier-{self.number + 1}"
        self.send("role_register", {"role_id": ident, "kind": "final_verifier", "context_id": ident,
            "fresh": True, "host": "codex", "launch_ref": "synthetic-unit-test",
            "capabilities": {"fresh_context": True}}, task_id=selected_task)
        result = self.conclude(role=ident, stage="final", outcome=outcome, task_id=selected_task)
        self.send("role_result", {"role_id": ident, "result": "DONE",
                                 "trace": "synthetic final assessment complete"}, task_id=selected_task)
        return result

    def review(self, role="reviewer", verdict="pass"):
        self.role(role, "reviewer")
        self.send("review_start", {"role_id": role})
        return self.send("review_result", {"role_id": role, "verdict": verdict, "findings": [], "test_integrity": "Assertions and skips inspected (unit fixture)", "trace": "unit-test"})

    def integrate(self, prefix=""):
        self.send("transfer")
        self.send("integrate")
        self.send("candidate")
        verifier = prefix + "integration-verifier"
        self.role(verifier, "verifier")
        result = self.run_checks("integration")
        assert result["outcome"] == "passed"
        self.conclude(role=verifier)
        self.review(prefix + "integration-reviewer")
        self.send("role_result", {"role_id": verifier, "result": "DONE", "trace": "unit-test"})
        return result


@pytest.fixture
def driver(basis):
    return Driver(basis)


@pytest.fixture(scope="session")
def execution_checkpoints(project_template, basis_template, repository_seeds, tmp_path_factory):
    from checkpoints import LazyCheckpoints
    from memory_repository import MemoryRepositories
    workspace = tmp_path_factory.mktemp("execution-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)
    basis = deepcopy(basis_template)
    basis.update(project_root=str(root), change_root=str(root / "sdd/changes/demo"))
    def steps():
        driver = Driver(basis)
        yield "pending", driver
        driver.start()
        assert not driver.state["blockers"]
        yield "started", driver
        (driver.root / "result.txt").write_text("verified result\n")
        driver.freeze()
        yield "frozen", driver
        assert driver.verify()["outcome"] == "passed"
        yield "verified", driver
        driver.role("reviewer", "reviewer")
        driver.send("review_start", {"role_id": "reviewer"})
        yield "reviewing", driver
        driver.send("review_result", {"role_id": "reviewer",
            "verdict": "pass", "findings": [], "test_integrity": "Fixture assertions preserved", "trace": "unit-test"})
        yield "worktree-reviewed", driver
        driver.integrate()
        yield "reviewed", driver
        driver.send("commit")
        assert driver.send("accept")["status"] == "accepted"
        driver.send("role_result", {"role_id": "verifier", "result": "DONE", "trace": "unit-test"})
        yield "accepted", driver
    return LazyCheckpoints(workspace, backend, steps())


@pytest.fixture
def execution_checkpoint(execution_checkpoints, repository_backend, state_backend):
    return lambda stage: execution_checkpoints[stage].restore(repository_backend, state_backend)
