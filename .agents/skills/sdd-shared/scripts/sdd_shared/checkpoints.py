"""Inspect, explicitly accept, and create Git checkpoint transitions."""
from __future__ import annotations

import re
from .checkpoint_git import Git, GitError


def classify(head, accepted_commit, changes, operation_in_progress=False):
    if operation_in_progress or any(c["status"] in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"} for c in changes):
        return "git_operation_in_progress"
    if head is None:
        return "unborn_head"
    if changes:
        return "dirty"
    if accepted_commit is None:
        return "acceptance_required"
    return "ready" if head == accepted_commit else "head_mismatch"


def _identity(work_kind, change_id):
    if work_kind not in ("change", "refactoring"):
        raise GitError("invalid_identity", "work_kind must be change or refactoring")
    if not isinstance(change_id, str) or len(change_id) > 64 or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", change_id):
        raise GitError("invalid_identity", "change_id must be a lowercase kebab-case slug of at most 64 characters")


def _result(operation, work_kind, change_id):
    return dict(schema_version=2, operation=operation, status="not_checked", work_kind=work_kind,
                change_id=change_id, checkpoint_ref=None, head=None, accepted_commit=None,
                dirty=False, changes=[], diagnostics=[], exit_code=0)


def _fail(result, code, message, exit_code=1):
    result.update(status=code, exit_code=exit_code)
    result["diagnostics"].append(dict(code=code, message=message,
                                     next_action="Inspect the repository again; preserve files and obtain a decision before recovery."))
    return result


def _observe(git, result):
    head, accepted, changes = git.head(), git.accepted(result["checkpoint_ref"]), git.changes()
    status = classify(head, accepted, changes, git.operation_in_progress())
    result.update(head=head, accepted_commit=accepted, changes=changes, dirty=bool(changes), status=status)
    return result


def _open(project_root, work_kind, change_id, result):
    _identity(work_kind, change_id)
    git = Git(project_root)
    result["checkpoint_ref"] = f"refs/sdd/checkpoints/{work_kind}/{change_id}/{git.worktree_key}"
    _observe(git, result)
    return git


def inspect(project_root, work_kind, change_id):
    result = _result("inspect", work_kind, change_id)
    try:
        git = _open(project_root, work_kind, change_id, result)
        if result["head"] and result["accepted_commit"] and result["head"] != result["accepted_commit"]:
            result["difference"] = git.difference(result["accepted_commit"], result["head"])
        return result
    except (GitError, OSError) as exc:
        return _fail(result, getattr(exc, "code", "git_error"), str(exc), 2)


def capture_changes(project_root):
    """Capture reviewed paths and tree in memory; never persist a document manifest."""
    return Git(project_root).capture()


def _expected(result, expected_head, expected_accepted):
    if not expected_head or result["head"] != expected_head or result["accepted_commit"] != expected_accepted:
        raise GitError("concurrent_change", "HEAD or accepted checkpoint differs from the expected observation")
    if result["status"] == "git_operation_in_progress":
        raise GitError("git_operation_in_progress", "Finish the ongoing Git operation before a checkpoint")


def _write_result(operation, work_kind, change_id, expected_accepted):
    result = _result(operation, work_kind, change_id)
    result.update(previous_accepted=expected_accepted, created_commit=None, ref_updated=False)
    return result


def _clean_at(result, oid):
    return result["head"] == oid and not result["dirty"] and result["status"] != "git_operation_in_progress"


def _finish(git, result, oid, old, message):
    git.update(result["checkpoint_ref"], oid, old, oid, message)
    result["ref_updated"] = True
    _observe(git, result)
    if not _clean_at(result, oid) or result["accepted_commit"] != oid:
        return _fail(result, "concurrent_change", "Repository changed after checkpoint reference update")
    result["status"] = "accepted" if result["operation"] == "accept" else "created"
    return result


def _write_error(git, result, exc):
    code = getattr(exc, "code", "git_error")
    if git is not None:
        try:
            _observe(git, result)
        except (GitError, OSError) as observation_error:
            result["diagnostics"].append(dict(code="observation_failed", message=str(observation_error), next_action="Run inspect again."))
    if result["ref_updated"]:
        code = "concurrent_change"
    elif result["created_commit"]:
        code = "commit_created_unaccepted"
    return _fail(result, code, str(exc), 2 if code in {"git_error", "git_unavailable", "not_repository", "invalid_checkpoint_ref", "unsupported_index_flags"} else 1)


def accept(project_root, work_kind, change_id, expected_head, expected_accepted, decision):
    result = _write_result("accept", work_kind, change_id, expected_accepted)
    git = None
    try:
        git = _open(project_root, work_kind, change_id, result)
        _expected(result, expected_head, expected_accepted)
        if not isinstance(decision, dict) or not all(isinstance(decision.get(k), str) and decision[k].strip() for k in ("id", "response", "source", "date")) or decision.get("accepted_commit") != expected_head:
            raise GitError("decision_required", "Supply the explicit user decision and its exact accepted_commit")
        if result["dirty"]:
            raise GitError("dirty", "Accepting HEAD does not accept uncommitted files")
        if expected_accepted == expected_head:
            _observe(git, result)
            _expected(result, expected_head, expected_accepted)
            if result["dirty"]:
                raise GitError("concurrent_change", "Repository became dirty during acceptance")
            result["status"] = "unchanged"
            return result
        message = f"SDD acceptance {decision['id']}: {decision['source']}".replace("\n", " ")
        return _finish(git, result, expected_head, expected_accepted, message)
    except (GitError, OSError) as exc:
        return _write_error(git, result, exc)


def _reviewed(git, reviewed_changes):
    if not isinstance(reviewed_changes, dict) or not isinstance(reviewed_changes.get("paths"), list):
        raise GitError("changes_changed", "Supply the reviewed paths and tree from capture_changes")
    current = git.capture()
    if current != reviewed_changes:
        raise GitError("changes_changed", "Repository paths or content changed since review")
    return current


def _commit(git, result, expected_head, reviewed, message):
    git.stage(reviewed["paths"])
    if git.run("write-tree").strip() != reviewed["tree"]:
        raise GitError("changes_changed", "Staged tree differs from the reviewed tree; index preserved")
    _observe(git, result)
    _expected(result, expected_head, expected_head)
    _reviewed(git, dict(reviewed, index_tree=reviewed["tree"]))
    outcome = git.commit(message)
    _observe(git, result)
    if result["head"] != expected_head:
        result["created_commit"] = result["head"]
    if outcome.returncode:
        raise GitError("commit_failed", outcome.stderr.decode("utf-8", errors="replace"))
    oid = result["created_commit"]
    if not oid or not _clean_at(result, oid) or not git.commit_matches(oid, expected_head, reviewed["tree"]):
        raise GitError("commit_created_unaccepted" if oid else "commit_failed", "Commit parent, tree, HEAD or cleanliness did not match the reviewed transition")
    return oid


def create(project_root, work_kind, change_id, expected_head, expected_accepted,
           reviewed_changes, instruction, message):
    result = _write_result("create", work_kind, change_id, expected_accepted)
    git = None
    try:
        git = _open(project_root, work_kind, change_id, result)
        _expected(result, expected_head, expected_accepted)
        if expected_head != expected_accepted:
            raise GitError("acceptance_required", "Creation requires HEAD to equal the accepted checkpoint")
        if not isinstance(instruction, dict) or not all(isinstance(instruction.get(k), str) and instruction[k].strip() for k in ("text", "source")):
            raise GitError("instruction_required", "An explicit work instruction with text and source is required")
        if not isinstance(message, str) or not message.strip():
            raise GitError("message_required", "Supply a nonempty commit message")
        reviewed = _reviewed(git, reviewed_changes)
        if not result["changes"]:
            _observe(git, result)
            _expected(result, expected_head, expected_accepted)
            if result["dirty"]:
                raise GitError("concurrent_change", "Repository changed during the empty transition")
            result["status"] = "unchanged"
            return result
        oid = _commit(git, result, expected_head, reviewed, message)
        return _finish(git, result, oid, expected_accepted, "SDD checkpoint")
    except (GitError, OSError) as exc:
        return _write_error(git, result, exc)
