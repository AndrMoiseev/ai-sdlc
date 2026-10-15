from copy import deepcopy
import json
from pathlib import Path

import pytest

from conftest import Driver
from lib.common import git
from lib.state import apply


def prepare(basis, tmp_path, paths=None):
    d = Driver(basis, parallel=True)
    old = Path(d.send("worktree_create", {"workspace": str(tmp_path / "trees")})["path"])
    d.start(paths or ["result.txt", "check.py"])
    (old / "result.txt").write_bytes(b"partial\x00binary\xff")
    d.send("role_result", {"role_id": "author", "result": "partial", "trace": "test-host"})
    return d, old


def fix_base(basis, name="external.txt", data="fixed"):
    root = Path(basis["project_root"])
    (root / name).write_text(data)
    git(root, "add", "--", name)
    git(root, "commit", "-m", "Fix pre-existing defect")
    return git(root, "rev-parse", "HEAD")


def refresh_event(d):
    state = d.state
    return {"event_id": "refresh-one", "run_id": state["run_id"], "expected_revision": state["revision"],
            "owner": state["owner"], "type": "worktree_refresh", "task_id": "TASK-one",
            "payload": {"reason": "Base defect fixed", "evidence": "fix commit and checks"}}


def test_refresh_preserves_changes_and_can_accept(basis, tmp_path):
    d, old = prepare(basis, tmp_path)
    d.send("candidate")
    d.verify()
    d.send("role_result", {"role_id": "verifier", "result": "checked", "trace": "test-host"})
    d.review()
    d.send("transfer")
    evidence, reviews = deepcopy(d.task["evidence"]), deepcopy(d.task["reviews"])
    head = fix_base(basis)
    root = Path(basis["project_root"])
    (root / "unrelated.txt").write_text("user staged work")
    git(root, "add", "unrelated.txt")
    index_before = git(root, "diff", "--cached", "--binary", raw=True)
    event = refresh_event(d)
    result = apply(d.directory, event)
    new = Path(result["worktree"]["path"])
    assert new != old and not old.exists()
    assert git(new, "rev-parse", "HEAD") == head
    assert not git(new, "symbolic-ref", "-q", "HEAD", check=False)
    assert (new / "external.txt").read_text() == "fixed"
    assert (new / "result.txt").read_bytes() == b"partial\x00binary\xff"
    assert d.task["candidate"] is None and "transfer" not in d.task
    assert d.task["status"] == "running"
    assert d.task["evidence"] == evidence and d.task["reviews"] == reviews
    assert d.task["review_rounds_started"] == 1
    assert apply(d.directory, event) == result
    assert len(d.task["worktree_history"]) == 1
    assert git(root, "diff", "--cached", "--binary", raw=True) == index_before
    d.send("candidate")  # New external file must not trip candidate_scope.
    d.verify("verifier-new")
    d.send("role_result", {"role_id": "verifier-new", "result": "checked", "trace": "test-host"})
    d.review("reviewer-new")
    d.send("transfer")
    d.send("integrate")
    d.send("candidate")
    d.role("integration-checker", "verifier")
    d.send("check_run", {"stage": "integration", "role_id": "integration-checker"})
    d.send("role_result", {"role_id": "integration-checker", "result": "checked", "trace": "test-host"})
    d.review("integration-reviewer")
    d.send("commit")
    d.send("accept")
    d.send("worktree_remove")
    assert d.task["status"] == "accepted" and not new.exists()
    assert git(root, "diff", "--cached", "--binary", raw=True) == index_before


@pytest.mark.parametrize("point", ["create", "before_apply", "apply", "remove", "state"])
def test_refresh_recovers_lost_response_at_each_effect(basis, tmp_path, monkeypatch, point):
    import lib.worktree_refresh as refresh
    import lib.state as state_module
    d, old = prepare(basis, tmp_path)
    fix_base(basis)
    event = refresh_event(d)
    original_git, original_write = refresh.git, state_module.write_json
    fired = False

    def crashing_git(root, *args, **kwargs):
        nonlocal fired
        if point == "before_apply" and args[:3] == ("apply", "--3way", "--index") and not fired:
            fired = True
            raise RuntimeError("simulated crash")
        result = original_git(root, *args, **kwargs)
        match = {"create": args[:2] == ("worktree", "add"),
                 "apply": args[:3] == ("apply", "--3way", "--index"),
                 "remove": args[:2] == ("worktree", "remove")}.get(point, False)
        if match and not fired:
            fired = True
            raise RuntimeError("simulated crash")
        return result

    def crashing_write(path, value):
        nonlocal fired
        if point == "state" and Path(path).name == "state.json" and not fired:
            fired = True
            raise RuntimeError("simulated crash")
        return original_write(path, value)

    monkeypatch.setattr(refresh, "git", crashing_git)
    monkeypatch.setattr(state_module, "write_json", crashing_write)
    with pytest.raises(RuntimeError, match="simulated crash"):
        apply(d.directory, event)
    result = apply(d.directory, event)
    assert not old.exists()
    assert Path(result["worktree"]["path"]).joinpath("result.txt").read_bytes() == b"partial\x00binary\xff"
    assert len(d.task["worktree_history"]) == 1


def test_conflict_preserves_both_trees_then_supported_resolution(basis, tmp_path):
    d, old = prepare(basis, tmp_path)
    (old / "check.py").write_text("assert 3 + 3 == 6\n")
    fix_base(basis, "check.py", "assert 4 + 4 == 8\n")
    event = refresh_event(d)
    with pytest.raises(ValueError):
        apply(d.directory, event)
    effect = d.directory / "runs" / d.state["run_id"] / "effects/refresh-one.json"
    saved = json.loads(effect.read_text())
    new = Path(saved["request"]["precondition"]["new"])
    assert old.exists() and new.exists() and git(new, "ls-files", "--unmerged")
    with pytest.raises(ValueError, match="pending worktree refresh"):
        d.send("candidate")
    with pytest.raises(ValueError, match="original refresh intent"):
        d.send("worktree_refresh", {"reason": "retry", "evidence": "fix"})
    role_result = d.role("resolver", "executor")
    packet = json.loads(Path(role_result["packet"]).read_text())
    assert packet["worktree_recovery"]["replacement"] == str(new)
    (new / "check.py").write_text("assert 4 + 4 == 8\nassert 3 + 3 == 6\n")
    git(new, "add", "check.py")
    d.send("role_result", {"role_id": "resolver", "result": "Both changes retained", "trace": "test-host"})
    result = d.send("worktree_refresh_resolve", {"intent_id": "refresh-one", "role_id": "resolver", "resolution": "Retained fix and task check"})
    assert result["worktree"]["path"] == str(new) and not old.exists()
    assert d.task["executor"] == "resolver"
    d.send("candidate")
    assert d.verify()["outcome"] == "passed"


@pytest.mark.parametrize("hazard", ["ignored", "writer", "commit", "blocked", "normative", "staged_foreign"])
def test_refresh_rejects_without_deleting_source(basis, tmp_path, hazard):
    d, old = prepare(basis, tmp_path)
    fix_base(basis)
    if hazard == "ignored":
        git(old, "config", "core.excludesFile", str(tmp_path / "ignore"))
        (tmp_path / "ignore").write_text("unknown.cache\n")
        (old / "unknown.cache").write_text("irreplaceable")
    elif hazard == "writer":
        d.role("writer-new", "executor")
    elif hazard == "commit":
        git(old, "add", "result.txt")
        git(old, "commit", "-m", "Unexpected executor commit")
    elif hazard == "blocked":
        d.send("block", {"reason": "external_defect", "resume_condition": "fixed"}, task_id=None)
    elif hazard == "staged_foreign":
        foreign = old / "sdd/changes/demo/proposal.md"
        original = foreign.read_bytes()
        foreign.write_text("staged user content")
        git(old, "add", "sdd/changes/demo/proposal.md")
        foreign.write_bytes(original)
    else:
        Path(basis["change_root"]).joinpath("design.md").write_text("drift")
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
                     "resolutions": [{"reason": "baseline_failed", "task_id": "TASK-one", "evidence": "Fix SHA; original failure passes"}]}, task_id=None)
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


def test_repeat_refresh_preserves_active_repair_and_reviews(basis, tmp_path):
    d, old = prepare(basis, tmp_path)
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
    second = d.send("worktree_refresh", {"reason": "Second base fix", "evidence": "Commit and checks"})
    assert not Path(first["worktree"]["path"]).exists()
    assert Path(second["worktree"]["path"]).joinpath("result.txt").read_bytes() == b"partial\x00binary\xff"
    assert len(d.task["worktree_history"]) == 2
    assert d.task["active_repair"] == "cycle-2" and d.task["test_repair_cycles_started"] == 2


def test_pending_worktree_can_refresh(basis, tmp_path):
    d = Driver(basis, parallel=True)
    d.send("worktree_create", {"workspace": str(tmp_path / "trees")})
    head = fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    assert d.task["status"] == "pending" and result["worktree"]["base"] == head
    d.start()


def test_refresh_before_any_task_edits(basis, tmp_path):
    d = Driver(basis, parallel=True)
    old = Path(d.send("worktree_create", {"workspace": str(tmp_path / "trees")})["path"])
    d.start(["result.txt", "check.py", "planned-but-not-created.txt"])
    d.send("role_result", {"role_id": "author", "result": "Stopped before edits", "trace": "test-host"})
    fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    assert not old.exists() and Path(result["worktree"]["path"]).joinpath("external.txt").exists()
    assert d.task["status"] == "running"


def test_refresh_preserves_deletions_modes_and_staged_history(basis, tmp_path):
    fix_base(basis, "obsolete.txt", "delete me")
    d, old = prepare(basis, tmp_path, ["result.txt", "check.py", "obsolete.txt", "future.txt"])
    (old / "obsolete.txt").unlink()
    (old / "check.py").chmod(0o755)
    git(old, "update-index", "--chmod=+x", "check.py")
    (old / "result.txt").write_text("staged version")
    git(old, "add", "result.txt")
    (old / "result.txt").write_text("working version")
    staged = git(old, "diff", "--cached", "--binary", "--full-index", raw=True)
    fix_base(basis)
    result = apply(d.directory, refresh_event(d))
    new = Path(result["worktree"]["path"])
    assert not (new / "obsolete.txt").exists()
    assert (new / "result.txt").read_text() == "working version"
    assert git(new, "ls-files", "--stage", "check.py").startswith("100755")
    artifact = d.directory / "runs" / d.state["run_id"] / "refresh/refresh-one/index.patch"
    assert artifact.read_bytes() == staged


def test_recovery_does_not_adopt_unrecorded_destination_edits(basis, tmp_path, monkeypatch):
    import lib.worktree_refresh as refresh
    d, old = prepare(basis, tmp_path)
    fix_base(basis)
    event = refresh_event(d)
    original = refresh.git

    def crash_after_apply(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        if args[:3] == ("apply", "--3way", "--index"):
            raise RuntimeError("crash")
        return result

    monkeypatch.setattr(refresh, "git", crash_after_apply)
    with pytest.raises(RuntimeError):
        apply(d.directory, event)
    monkeypatch.setattr(refresh, "git", original)
    effect = d.directory / "runs" / d.state["run_id"] / "effects/refresh-one.json"
    new = Path(json.loads(effect.read_text())["request"]["precondition"]["new"])
    (new / "check.py").write_text("assert True\n# unrecorded edit after crash\n")
    with pytest.raises(ValueError, match="differs from the recorded merge"):
        apply(d.directory, event)
    assert old.exists() and new.exists()


def test_unresolved_integration_is_not_refreshed(basis, tmp_path):
    d, old = prepare(basis, tmp_path)
    d.send("candidate")
    d.verify()
    d.send("role_result", {"role_id": "verifier", "result": "checked", "trace": "test-host"})
    d.review()
    d.send("transfer")
    fix_base(basis, "result.txt", "conflicting root result")
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
    fix_base(basis, "check.py", initial.replace("# four", "# external fix"))
    event = refresh_event(d)
    original = refresh.git

    def crash_after_apply(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        if args[:3] == ("apply", "--3way", "--index"):
            raise RuntimeError("crash")
        return result

    monkeypatch.setattr(refresh, "git", crash_after_apply)
    with pytest.raises(RuntimeError):
        apply(d.directory, event)
    monkeypatch.setattr(refresh, "git", original)
    result = apply(d.directory, event)
    text = Path(result["worktree"]["path"]).joinpath("check.py").read_text()
    assert "# task edit" in text and "# external fix" in text and not old.exists()
