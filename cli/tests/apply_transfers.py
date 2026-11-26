"""Compare E22–E25 with real Git worktrees, refs, binary patches and conflicts."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

from apply import ApplyHarness
from pilot import PilotFailure, compare_stdout, file_digest, run, time_remaining


SOURCE = b"assert 3 + 3 == 6\n"
CONCURRENT = b"assert 4 + 4 == 8\n"
RESOLVED = CONCURRENT + SOURCE
BINARY = b"\x00\xffbinary transfer\n"


@dataclass(frozen=True)
class ReviewedSeed:
    directory: Path
    repositories: tuple[Path, Path]
    source: Path


def need(condition, message):
    if not condition:
        raise PilotFailure(message)


def git(harness, path, *args):
    result = run(["git", "-C", str(path), *args], harness.cwd, harness.deadline)
    need(result.returncode == 0, f"Git {args!r} in {path}: {result.stderr!r}")
    return result.stdout


def head(harness, path):
    return git(harness, path, "rev-parse", "HEAD").decode().strip()


def status(harness, path):
    relative = harness.execution.relative_to(harness.project).as_posix()
    return git(harness, path, "status", "--short", "--untracked-files=all", "--", ".", f":(exclude){relative}").decode().splitlines()


def commit(harness, path, name, contents):
    (path / name).write_bytes(contents)
    git(harness, path, "add", "--", name)
    git(harness, path, "commit", "-m", "Concurrent accepted fixture")
    return head(harness, path)


def adopt_main_head(runner, new_head):
    runner.send("resume", {
        "host_trace": "fixture host", "live_contexts": [],
        "resolutions": [{
            "reason": "execution_head_changed", "head": new_head,
            "evidence": "Inspected independent fixture commit", "compatible": True,
        }],
    }, task_id=None)
    need(runner.state["execution_head"] == new_head, "execution head was not reconciled")


def effect(harness, runner, operation):
    path = harness.execution / "runs" / runner.state["run_id"] / "effects" / (operation + ".json")
    return json.loads(path.read_bytes())


def budgets(task):
    return {key: task[key] for key in (
        "attempt", "review_limit", "review_rounds_started", "review_rounds_completed",
        "test_repair_limit", "test_repair_cycles_started", "budget_decisions",
    )}


def package(harness, runner, source, existing=None):
    transfer = existing if existing is not None else runner.send("transfer")
    patch_path = harness.execution / transfer["path"]
    manifest = patch_path.with_name(patch_path.name + ".json")
    raw = patch_path.read_bytes()
    source_commit, source_tree = git(harness, source, "rev-parse", "HEAD", "HEAD^{tree}").decode().splitlines()
    need(transfer["commit"] == source_commit and transfer["sha256"] == hashlib.sha256(raw).hexdigest() and
         transfer["tree"] == source_tree and
         raw == git(harness, source, "diff", "--binary", "--full-index", transfer["base"], transfer["tree"]) and
         b"GIT binary patch" in raw and json.loads(manifest.read_bytes()) == transfer,
         "transfer does not bind the exact binary patch, candidate, tree and retained evidence")
    return transfer, patch_path, raw


def integrate_binary(harness, runner, source, on_transfer=None):
    main = harness.project
    original_head = head(harness, main)
    evidence = runner.task["evidence"]
    transfer, patch_path, raw = package(harness, runner, source)
    if on_transfer is not None:
        on_transfer()
    patch_path.write_bytes(raw + b"corruption")
    rejection = runner.send("integrate", error="transfer_corrupt")
    need(head(harness, main) == original_head and not status(harness, main), "bad transfer dirtied execution tree")
    patch_path.write_bytes(raw)
    result = runner.send("integrate")
    current = runner.task
    changed = git(harness, main, "diff", "--cached", "--binary", "--full-index", "HEAD")
    need((main / "result.bin").read_bytes() == BINARY and (main / "check.py").read_bytes() == SOURCE and
         result["head"] == original_head and current["worktree"]["integration_tree"] == transfer["tree"] and
         current["integration_active"] and current["evidence"] == evidence and changed == raw,
         "integration did not apply the verified binary transfer and preserve verification")
    return [transfer, rejection, result, current["worktree"], changed]


def refresh_clean(harness, runner, source):
    main = harness.project
    new_base = commit(harness, main, "external.txt", b"accepted external fix\n")
    adopt_main_head(runner, new_base)
    before = runner.task
    source_head = before["candidate_commit"]["sha"]
    review_budget = budgets(before)
    result = runner.send("worktree_refresh", {"reason": "Accepted new base", "evidence": "Reviewed external fix"})
    new = Path(result["worktree"]["path"])
    after = runner.task
    need(new != source and source.is_dir() and head(harness, source) == source_head and head(harness, new) == new_base and
         (new / "external.txt").read_bytes() == b"accepted external fix\n" and (new / "check.py").read_bytes() == SOURCE and
         (new / "result.bin").read_bytes() == BINARY and (source / "result.bin").read_bytes() == BINARY and
         not status(harness, main) and len(after["worktree_history"]) == 1 and budgets(after) == review_budget and
         after["status"] == "running" and "candidate_commit" not in after and after["evidence"] == before["evidence"],
         "refresh did not preserve both trees, candidate evidence and budgets")
    review = {key: after[key] for key in ("status", "worktree_history", "reviews")}
    return [result, review_budget, review, status(harness, new)]


def integrate_conflict_and_resolve(harness, runner, source):
    main = harness.project
    transfer, _, _ = package(harness, runner, source, existing=runner.task.get("transfer"))
    base = commit(harness, main, "check.py", CONCURRENT)
    adopt_main_head(runner, base)
    original_index = git(harness, main, "write-tree")
    conflict = runner.send("integrate")
    need(conflict["status"] == "conflict" and conflict["next"] == "worktree_refresh" and
         conflict["before"] == conflict["after"] and conflict["head"] == base and not status(harness, main) and
         git(harness, main, "write-tree") == original_index and (main / "check.py").read_bytes() == CONCURRENT and
         not (main / "result.bin").exists(), "integration conflict left changes on execution branch")
    before = runner.task
    old_head = transfer["commit"]
    revision = runner.state["revision"]
    intent = f"worktree_refresh-{revision}"
    refresh_error = runner.send("worktree_refresh", {"reason": "Integration conflict", "evidence": conflict},
                                error="git_failed")
    journal = effect(harness, runner, intent)
    saved = journal["request"]["precondition"]
    replacement = Path(saved["new"])
    pending = git(harness, replacement, "ls-files", "--unmerged").decode().splitlines()
    need(journal["phase"] == "prepared" and journal["apply_started"] and journal["expected_tree"] is None and
         saved["source_commit"] == old_head and file_digest(Path(saved["patch"])) == saved["patch_hash"] and
         runner.state["revision"] == revision and bool(pending) and replacement.is_dir() and source.is_dir() and
         (source / "check.py").read_bytes() == SOURCE and not status(harness, main),
         "conflicted refresh did not retain intent, both trees and true Git conflicts")
    runner.role("resolver", "executor")
    (replacement / "check.py").write_bytes(RESOLVED)
    git(harness, replacement, "add", "check.py")
    runner.send("role_result", {"role_id": "resolver", "result": "Retained both changes", "trace": "fixture resolver completed"})
    result = runner.send("worktree_refresh_resolve", {
        "intent_id": intent, "role_id": "resolver", "resolution": "Both changes retained",
    })
    after = runner.task
    observed = effect(harness, runner, intent)
    need(result["worktree"]["path"] == str(replacement) and result["retained"] == str(source) and
         observed["phase"] == "observed" and observed["result"]["tree"] == result["tree"] and
         after["executor"] == "resolver" and after["status"] == "running" and budgets(after) == budgets(before) and
         "transfer" not in after and "candidate_commit" not in after and not git(harness, replacement, "ls-files", "--unmerged") and
         (replacement / "check.py").read_bytes() == RESOLVED and (replacement / "result.bin").read_bytes() == BINARY and
         (source / "check.py").read_bytes() == SOURCE and head(harness, source) == old_head and not status(harness, main),
         "resolution failed to adopt the registered replacement with preserved budgets and source")
    return [transfer, conflict, refresh_error, journal, pending, result, observed["result"], budgets(after)]


def copy_repository(source, destination, object_stores):
    # Git loose objects and SDD objects are content-addressed. Worktree files,
    # refs, indexes, transfer patches and all other artifacts need private copies.
    def copy_entry(path, target):
        bucket = Path(path).parent
        if len(bucket.name) == 2 and all(char in "0123456789abcdef" for char in bucket.name) and bucket.parent in object_stores:
            try:
                return os.link(path, target)
            except OSError:
                pass
        return shutil.copy2(path, target)

    shutil.copytree(source, destination, symlinks=True, copy_function=copy_entry)


def object_stores(harness, project):
    execution = harness.execution.relative_to(harness.project)
    return {project / ".git" / "objects", project / execution / "objects"}


def capture_reviewed_seed(harness, driver):
    task = driver.task
    need(task["status"] == "integrating" and task["worktree"] and not task["worktree"]["integrated"],
         "fixture needs a reviewed, unintegrated task")
    worktree = task["worktree"]
    source = Path(worktree["path"])
    need((source / "result.bin").read_bytes() == BINARY and (source / "check.py").read_bytes() == SOURCE,
         "reviewed fixture needs the binary transfer and a conflicting tracked edit")
    directory = Path(tempfile.mkdtemp(prefix="reviewed-transfer-", dir=harness.workspace))
    repositories = (harness.project, Path(worktree["workspace"]))
    for index, repository in enumerate(repositories):
        copy_repository(repository, directory / str(index), object_stores(harness, harness.project))
    return ReviewedSeed(directory, repositories, source)


@contextmanager
def preserve_repositories(workspace, repositories, prefix):
    backup = Path(tempfile.mkdtemp(prefix=prefix, dir=workspace))
    moved = []
    try:
        for index, repository in enumerate(repositories):
            if repository.exists():
                saved = backup / str(index)
                repository.rename(saved)
                moved.append((repository, saved))
        yield
    finally:
        for repository, saved in moved:
            saved.rename(repository)


@contextmanager
def restore_reviewed_seed(harness, seed):
    observed = Path(tempfile.mkdtemp(prefix="transfer-observed-", dir=harness.workspace))
    try:
        for index, repository in enumerate(seed.repositories):
            copy_repository(seed.directory / str(index), repository, object_stores(harness, seed.directory / "0"))
        yield
    finally:
        for index, repository in enumerate(seed.repositories):
            if repository.exists():
                repository.rename(observed / str(index))


def prepare_reviewed_seed(harness, driver_type):
    harness.fixture()
    harness.initialized("Python")
    driver = driver_type(harness, "Python")
    driver.begin(paths=["result.bin", "check.py"])
    (driver.root / "result.bin").write_bytes(BINARY)
    (driver.root / "check.py").write_bytes(SOURCE)
    driver.freeze()
    driver.verify()
    return capture_reviewed_seed(harness, driver)


def compare_scenario(harness, seed, driver_type, family, scenario):
    output = []
    for implementation in harness.commands:
        time_remaining(harness.deadline)
        with restore_reviewed_seed(harness, seed):
            driver = driver_type(harness, implementation)
            try:
                output.append(scenario(harness, driver, seed.source))
            except Exception as exc:
                raise PilotFailure(f"{family} {implementation}: {exc}") from exc
    compare_stdout(*output)
    print(f"{family} PASS", flush=True)


def git_transition_cases(harness, reviewed_seed=None, *, include_binary=True):
    from apply_events import Driver

    with patch.dict(os.environ, {
        "GIT_AUTHOR_DATE": "2026-11-01T11:15:00+00:00", "GIT_COMMITTER_DATE": "2026-11-01T11:15:00+00:00",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(harness.workspace / "empty-git-config"),
    }):
        seed = reviewed_seed or prepare_reviewed_seed(harness, Driver)
        transferred_seed = None
        started = time.monotonic()
        with preserve_repositories(harness.workspace, seed.repositories, "transfer-fixture-"):
            if include_binary:
                def binary_scenario(h, runner, source):
                    def capture():
                        nonlocal transferred_seed
                        if runner.implementation == "Python":
                            transferred_seed = capture_reviewed_seed(h, runner)
                    return integrate_binary(h, runner, source, on_transfer=capture)

                compare_scenario(harness, seed, Driver, "E24–E25 binary success", binary_scenario)
                seed = transferred_seed
            refresh_started = time.monotonic()
            compare_scenario(harness, seed, Driver, "E22 successful refresh", refresh_clean)
            compare_scenario(harness, seed, Driver, "E22–E23, E25 conflict and resolution", integrate_conflict_and_resolve)
            print(f"Apply refresh and conflict elapsed {time.monotonic() - refresh_started:.2f} s using the reviewed seed", flush=True)
        print(f"Apply transfer cases elapsed {time.monotonic() - started:.2f} s using the reviewed seed", flush=True)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=118)
    args = parser.parse_args()
    if not 0 < args.timeout <= 120 or not args.python.is_absolute():
        parser.error("Use an absolute interpreter and a timeout between 0 and 120 seconds")
    base = args.basetemp.resolve()
    if not base.is_dir() or any((parent / ".git").exists() for parent in (base, *base.parents)):
        parser.error("Use an existing temporary directory outside Git worktrees")
    workspace = Path(tempfile.mkdtemp(prefix="sdd-apply-transfers-", dir=base))
    print(f"Apply transfer workspace {workspace}", flush=True)
    try:
        harness = ApplyHarness(workspace, args.repository, args.python, started + args.timeout)
        git_transition_cases(harness)
        time_remaining(harness.deadline)
    except (AssertionError, PilotFailure, OSError, TimeoutError, ValueError) as exc:
        print(f"Apply transfer parity failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Apply transfers elapsed {time.monotonic() - started:.2f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
