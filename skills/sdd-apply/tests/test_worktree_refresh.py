from lib import artifact_storage as artifacts
from lib.repository import repository
from repository_support import stage as stage_files, commit, set_mode, ignore, file_mode
from copy import deepcopy
import json
from pathlib import Path

import pytest

from conftest import Driver

from lib.state import apply


def prepare(basis, tmp_path, paths=None):
    basis = deepcopy(basis)
    basis["head"] = repository(basis["project_root"]).head()
    d = Driver(basis)
    old = Path(d.send("worktree_create", {"workspace": str(tmp_path / "trees")})["path"])
    d.start(paths or ["result.txt", "check.py"])
    (old / "result.txt").write_bytes(b"partial\x00binary\xff")
    stage_files(old, "result.txt")
    commit(old, "Local partial candidate")
    d.send("role_result", {"role_id": "author", "result": "partial", "trace": "test-host"})
    return d, old


def fix_base(basis, name="external.txt", data="fixed"):
    root = Path(basis["project_root"])
    (root / name).write_text(data)
    stage_files(root, name)
    commit(root, "Fix pre-existing defect")
    return repository(root).head()


def accept_source(d):
    head = repository(d.state["basis"]["project_root"]).head()
    if head != d.state["execution_head"]:
        d.send("resume", {"host_trace": "synthetic fixture", "live_contexts": [r["context_id"] for r in d.state["roles"].values() if r["status"] == "active"],
            "resolutions": [{"reason": "execution_head_changed", "head": head, "evidence": "Inspected external fix",
                             "instruction": {"text": "Accept fixed source", "source": "synthetic-user"}}]}, task_id=None)


def refresh_event(d):
    accept_source(d)
    state = d.state
    return {"event_id": "refresh-one", "run_id": state["run_id"], "expected_revision": state["revision"],
            "type": "worktree_refresh", "task_id": "TASK-one",
            "payload": {"reason": "Base defect fixed", "evidence": "fix commit and checks"}}


@pytest.fixture(scope="session")
def refresh_template(project_template, basis_template, repository_seeds, tmp_path_factory):
    from checkpoints import Checkpoint, preparation
    from conftest import copy_project
    from memory_repository import MemoryRepositories
    workspace = tmp_path_factory.mktemp("refresh-checkpoint")
    backend = MemoryRepositories(repository_seeds)
    root = copy_project(project_template, workspace / "project", backend)
    basis = deepcopy(basis_template)
    basis.update(project_root=str(root), change_root=str(root / "sdd/changes/demo"))
    with preparation(backend) as states:
        driver, _ = prepare(basis, workspace)
        return Checkpoint(workspace, driver, backend, states)


@pytest.fixture
def refresh_checkpoint(refresh_template, repository_backend, state_backend):
    driver = refresh_template.restore(repository_backend, state_backend)
    return driver, Path(driver.task["worktree"]["path"]), driver.state["basis"]


def test_refresh_preserves_changes_and_can_accept(basis, tmp_path):
    d, old = prepare(basis, tmp_path)
    d.send("candidate")
    d.verify()
    d.send("role_result", {"role_id": "verifier", "result": "checked", "trace": "test-host"})
    d.review()
    d.send("transfer")
    evidence, reviews = deepcopy(d.task["evidence"]), deepcopy(d.task["reviews"])
    head = fix_base(basis)
    accept_source(d)
    root = Path(basis["project_root"])
    (root / "unrelated.txt").write_text("user staged work")
    stage_files(root, "unrelated.txt")
    index_before = repository(root).index_patch()
    event = refresh_event(d)
    result = apply(d.directory, event)
    new = Path(result["worktree"]["path"])
    assert new != old and old.exists()
    assert repository(new).head() == head
    assert repository(new).branch() == result["worktree"]["branch"]
    assert (new / "external.txt").read_text() == "fixed"
    assert (new / "result.txt").read_bytes() == b"partial\x00binary\xff"
    assert "candidate" not in d.task and "transfer" not in d.task
    assert d.task["status"] == "running"
    assert d.task["evidence"] == evidence and d.task["reviews"] == reviews
    assert d.task["review_rounds_started"] == 1
    assert apply(d.directory, event) == result
    assert len(d.task["worktree_history"]) == 1
    assert repository(root).index_patch() == index_before
    commit(root, "User work committed before integration")
    accept_source(d)
    d.send("candidate")  # New external file must not trip candidate_scope.
    d.verify("verifier-new")
    d.send("role_result", {"role_id": "verifier-new", "result": "checked", "trace": "test-host"})
    d.review("reviewer-new")
    d.send("transfer")
    d.send("integrate")
    d.send("candidate")
    d.role("integration-checker", "verifier")
    d.run_checks("integration")
    d.conclude(role="integration-checker")
    d.send("role_result", {"role_id": "integration-checker", "result": "checked", "trace": "test-host"})
    d.review("integration-reviewer")
    d.send("commit")
    d.send("accept")
    d.send("worktree_remove")
    assert d.task["status"] == "accepted" and not new.exists()
    assert repository(root).content("HEAD", "unrelated.txt") == b"user staged work"


@pytest.mark.parametrize("point", ["create", "before_apply", "apply", "state"])
def test_refresh_recovers_lost_response_at_each_effect(refresh_checkpoint, monkeypatch, point):
    import lib.worktree_refresh as refresh
    import lib.state as state_module
    d, old, basis = refresh_checkpoint
    fix_base(basis)
    event = refresh_event(d)
    original_write = state_module.save
    fired = False

    operation = {"create": "create_worktree", "before_apply": "apply_patch", "apply": "apply_patch", "remove": "remove_worktree"}.get(point)
    repo = repository(basis["project_root"])
    original_operation = getattr(type(repo), operation) if operation else None

    def crashing_operation(self, *args, **kwargs):
        nonlocal fired
        if point == "before_apply" and not fired:
            fired = True
            raise RuntimeError("simulated crash")
        result = original_operation(self, *args, **kwargs)
        if not fired:
            fired = True
            raise RuntimeError("simulated crash")
        return result

    def crashing_write(path, value):
        nonlocal fired
        if point == "state" and not fired:
            fired = True
            raise RuntimeError("simulated crash")
        return original_write(path, value)

    if operation:
        monkeypatch.setattr(type(repo), operation, crashing_operation)
    monkeypatch.setattr(state_module, "save", crashing_write)
    with pytest.raises(RuntimeError, match="simulated crash"):
        apply(d.directory, event)
    result = apply(d.directory, event)
    assert old.exists()
    assert Path(result["worktree"]["path"]).joinpath("result.txt").read_bytes() == b"partial\x00binary\xff"
    assert len(d.task["worktree_history"]) == 1


def test_conflict_preserves_both_trees_then_supported_resolution(refresh_checkpoint):
    d, old, basis = refresh_checkpoint
    (old / "check.py").write_text("assert 3 + 3 == 6\n")
    stage_files(old, "check.py")
    commit(old, "Task check change")
    fix_base(basis, "check.py", "assert 4 + 4 == 8\n")
    event = refresh_event(d)
    with pytest.raises(ValueError):
        apply(d.directory, event)
    effect = d.directory / "runs" / d.state["run_id"] / "effects/refresh-one.json"
    saved = json.loads(artifacts.read_bytes(effect))
    new = Path(saved["request"]["precondition"]["new"])
    assert old.exists() and new.exists() and repository(new).has_conflicts()
    with pytest.raises(ValueError, match="pending worktree refresh"):
        d.send("candidate")
    with pytest.raises(ValueError, match="original refresh intent"):
        d.send("worktree_refresh", {"reason": "retry", "evidence": "fix"})
    role_result = d.role("resolver", "executor")
    packet = json.loads(artifacts.read_text(role_result["packet"]))
    assert packet["worktree_recovery"]["replacement"] == str(new)
    (new / "check.py").write_text("assert 4 + 4 == 8\nassert 3 + 3 == 6\n")
    stage_files(new, "check.py")
    d.send("role_result", {"role_id": "resolver", "result": "Both changes retained", "trace": "test-host"})
    result = d.send("worktree_refresh_resolve", {"intent_id": "refresh-one", "role_id": "resolver", "resolution": "Retained fix and task check"})
    assert result["worktree"]["path"] == str(new) and old.exists()
    assert d.task["executor"] == "resolver"
    d.send("candidate")
    assert d.verify()["outcome"] == "passed"


@pytest.mark.parametrize("hazard", ["ignored", "writer", "foreign_commit", "blocked", "normative", "staged_foreign", "uncommitted"])
def test_refresh_rejects_without_deleting_source(refresh_checkpoint, hazard):
    d, old, basis = refresh_checkpoint
    fix_base(basis)
    accept_source(d)
    if hazard == "ignored":
        ignore(old, "unknown.cache")
        (old / "unknown.cache").write_text("irreplaceable")
    elif hazard == "writer":
        d.role("writer-new", "executor")
    elif hazard == "foreign_commit":
        (old / "foreign.txt").write_text("outside task")
        stage_files(old, "foreign.txt")
        commit(old, "Unexpected foreign commit")
    elif hazard == "uncommitted":
        (old / "check.py").write_text("uncommitted task change")
    elif hazard == "blocked":
        d.send("block", {"reason": "external_defect", "resume_condition": "fixed"}, task_id=None)
    elif hazard == "staged_foreign":
        foreign = old / "sdd/changes/demo/proposal.md"
        original = foreign.read_bytes()
        foreign.write_text("staged user content")
        stage_files(old, "sdd/changes/demo/proposal.md")
        foreign.write_bytes(original)
    else:
        Path(basis["change_root"]).joinpath("design.md").write_text("drift")
    if hazard == "normative":
        admitted = d.state["basis"]["head"]
        apply(d.directory, refresh_event(d))
        assert d.state["basis"]["head"] == admitted
        assert Path(basis["change_root"]).joinpath("design.md").read_text() == "drift"
        assert old.exists()
        return
    with pytest.raises(ValueError):
        apply(d.directory, refresh_event(d))
    assert old.exists() and (old / "result.txt").read_bytes() == b"partial\x00binary\xff"
    assert d.task["worktree"]["path"] == str(old)


def test_baseline_failure_resumes_on_fixed_base_with_same_budget(basis, tmp_path):
    fix_base(basis, "check.py", "assert False\n")
    d, old = prepare(basis, tmp_path)
    assert d.state["status"] == "blocked" and d.task["last_check_failed"]
    fix_base(basis, "check.py", "assert True\n")
    resumed = d.send("resume", {"host_trace": "all roles stopped", "live_contexts": [],
                     "resolutions": [{"reason": "baseline_failed", "task_id": "TASK-one", "evidence": "Fix SHA; original failure passes"},
                                     {"reason": "execution_head_changed", "head": repository(basis["project_root"]).head(),
                                      "evidence": "Inspected external fix", "instruction": {"text": "Accept fixed source", "source": "synthetic-user"}}]}, task_id=None)
    assert resumed["stale_worktrees"][0]["task_id"] == "TASK-one"
    assert resumed["stale_worktrees"][0]["next"] == "worktree_refresh"
    apply(d.directory, refresh_event(d))
    assert d.send("resume", {"host_trace": "all stopped", "live_contexts": []}, task_id=None)["stale_worktrees"] == []
    d.send("repair", {"reason": "Retry after external base fix"})
    assert d.task["test_repair_cycles_started"] == 1
    d.send("role_result", {"role_id": "author", "result": "Changes ready", "trace": "test-host"})
    d.send("candidate")
    assert d.verify()["outcome"] == "passed"
    assert d.task["test_repair_cycles_started"] == 1 and d.task["active_repair"] is None
    assert d.task["baseline_checks"] == d.task["worktree_history"][0]["baseline_checks"]


def test_repeat_refresh_preserves_active_repair_and_reviews(refresh_checkpoint):
    d, old, basis = refresh_checkpoint
    d.send("repair", {"reason": "Test defect", "defect_evidence": "failure trace", "test_failure": True})
    d.send("role_result", {"role_id": "author", "result": "partial", "trace": "test-host"})
    d.send("candidate")
    d.verify()
    d.send("role_result", {"role_id": "verifier", "result": "checked", "trace": "test-host"})
    d.role("reviewer", "reviewer")
    d.send("review_start", {"role_id": "reviewer"})
    d.send("role_result", {"role_id": "reviewer", "result": "interrupted", "trace": "test-host"})
    d.send("repair", {"reason": "Another failure", "defect_evidence": "failure trace", "test_failure": True})
    d.send("role_result", {"role_id": "author", "result": "partial", "trace": "test-host"})
    fix_base(basis)
    first = apply(d.directory, refresh_event(d))
    assert d.task["active_review"] is None and d.task["review_rounds_started"] == 1
    assert d.task["active_repair"] == "cycle-2" and d.task["test_repair_cycles_started"] == 2
    fix_base(basis, "external.txt", "second fix")
    first_root = Path(first["worktree"]["path"])
    stage_files(first_root, "result.txt")
    commit(first_root, "Rebased task candidate")
    accept_source(d)
    second = d.send("worktree_refresh", {"reason": "Second base fix", "evidence": "Commit and checks"})
    assert Path(first["worktree"]["path"]).exists()
    assert Path(second["worktree"]["path"]).joinpath("result.txt").read_bytes() == b"partial\x00binary\xff"
    assert len(d.task["worktree_history"]) == 2
    assert d.task["active_repair"] == "cycle-2" and d.task["test_repair_cycles_started"] == 2


def test_pending_worktree_can_refresh(basis, tmp_path):
    d = Driver(basis)
    d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    head = fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    assert d.task["status"] == "pending" and result["worktree"]["base"] == head
    d.start()


def test_refresh_before_any_task_edits(basis, tmp_path):
    d = Driver(basis)
    old = Path(d.send("worktree_create", {"workspace": str(tmp_path / "trees")})["path"])
    d.start(["result.txt", "check.py", "planned-but-not-created.txt"])
    d.send("role_result", {"role_id": "author", "result": "Stopped before edits", "trace": "test-host"})
    fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    assert old.exists() and Path(result["worktree"]["path"]).joinpath("external.txt").exists()
    assert d.task["status"] == "running"


def test_refresh_preserves_committed_deletions_modes_and_content(basis, tmp_path):
    fix_base(basis, "obsolete.txt", "delete me")
    d, old = prepare(basis, tmp_path, ["result.txt", "check.py", "obsolete.txt", "future.txt"])
    (old / "obsolete.txt").unlink()
    (old / "check.py").chmod(0o755)
    set_mode(old, "check.py", True)
    (old / "result.txt").write_text("working version")
    stage_files(old, "result.txt", "obsolete.txt", "check.py")
    commit(old, "Committed complete task change")
    fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    new = Path(result["worktree"]["path"])
    assert not (new / "obsolete.txt").exists()
    assert (new / "result.txt").read_text() == "working version"
    assert file_mode(new, "check.py") == "100755"
    assert repository(old).content("HEAD", "result.txt") == b"working version"
    assert old.exists()


def test_recovery_does_not_adopt_unrecorded_destination_edits(refresh_checkpoint, monkeypatch):
    import lib.worktree_refresh as refresh
    d, old, basis = refresh_checkpoint
    fix_base(basis)
    event = refresh_event(d)
    adapter = type(repository(basis["project_root"]))
    original = adapter.apply_patch

    def crash_after_apply(self, patch):
        original(self, patch)
        raise RuntimeError("crash")

    monkeypatch.setattr(adapter, "apply_patch", crash_after_apply)
    with pytest.raises(RuntimeError):
        apply(d.directory, event)
    monkeypatch.setattr(adapter, "apply_patch", original)
    effect = d.directory / "runs" / d.state["run_id"] / "effects/refresh-one.json"
    new = Path(json.loads(artifacts.read_bytes(effect))["request"]["precondition"]["new"])
    (new / "check.py").write_text("assert True\n# unrecorded edit after crash\n")
    with pytest.raises(ValueError, match="differs from recorded Git merge"):
        apply(d.directory, event)
    assert old.exists() and new.exists()


def test_unresolved_integration_is_not_refreshed(refresh_checkpoint):
    d, old, basis = refresh_checkpoint
    d.send("candidate")
    d.verify()
    d.send("role_result", {"role_id": "verifier", "result": "checked", "trace": "test-host"})
    d.review()
    d.send("transfer")
    fix_base(basis, "result.txt", "conflicting root result")
    accept_source(d)
    with pytest.raises(ValueError):
        d.send("integrate")
    with pytest.raises(ValueError, match="pending integration"):
        apply(d.directory, refresh_event(d))
    assert old.exists()


def test_retry_after_three_way_merge_with_changed_patch_context(basis, tmp_path, monkeypatch):
    import lib.worktree_refresh as refresh
    initial = "# one\n# two\n# three\n# four\nassert True\n"
    fix_base(basis, "check.py", initial)
    d, old = prepare(basis, tmp_path)
    (old / "check.py").write_text(initial.replace("# two", "# task edit"))
    stage_files(old, "check.py")
    commit(old, "Task edit before refresh")
    fix_base(basis, "check.py", initial.replace("# four", "# external fix"))
    event = refresh_event(d)
    adapter = type(repository(basis["project_root"]))
    original = adapter.apply_patch

    def crash_after_apply(self, patch):
        original(self, patch)
        raise RuntimeError("crash")

    monkeypatch.setattr(adapter, "apply_patch", crash_after_apply)
    with pytest.raises(RuntimeError):
        apply(d.directory, event)
    monkeypatch.setattr(adapter, "apply_patch", original)
    result = apply(d.directory, event)
    text = Path(result["worktree"]["path"]).joinpath("check.py").read_text()
    assert "# task edit" in text and "# external fix" in text and old.exists()
