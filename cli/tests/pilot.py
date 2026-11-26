"""Compare the Go check command with the pinned Python entry point (P01–P08)."""

import argparse
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile


PYTHON_COMMIT = "89b40724dfaa44259dcf64781f30493b42b52191"
TIME_LIMIT = 120
CHANGE_ID = "sample-change"
MISSING = object()


class PilotFailure(Exception):
    pass


@dataclass(frozen=True)
class Scenario:
    id: str
    stage: str
    exit_code: int
    edit: str = ""


SCENARIOS = (
    Scenario("P01", "documents", 0),
    Scenario("P02", "plan", 0),
    Scenario("P03", "documents", 0, "missing_tasks"),
    Scenario("P04", "plan", 2, "missing_tasks"),
    Scenario("P05", "plan", 1, "task_number"),
    Scenario("P06", "documents", 2, "missing_proposal"),
    Scenario("P07", "documents", 2, "proposal_version"),
    Scenario("P08", "documents", 2, "proposal_encoding"),
)


def time_remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("pilot deadline exceeded")
    return remaining


def run(command, cwd, deadline):
    time_remaining(deadline)
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt"
               else {"start_new_session": True})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, **options) as process:
        try:
            stdout, stderr = process.communicate(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=5, **options)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if process.poll() is None:
                    process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            raise TimeoutError(f"pilot deadline exceeded while running {command!r}") from exc
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def prepare_baseline(repository, workspace, deadline, skills=("sdd-spec", "sdd-shared")):
    command = ["git", "-C", str(repository), "archive", "--format=zip", PYTHON_COMMIT,
               *(f"skills/{name}" for name in skills)]
    archive = run(command, workspace, deadline)
    if archive.returncode:
        raise PilotFailure(f"{command!r} exited {archive.returncode}: {archive.stderr!r}")
    baseline = workspace / "python baseline"
    with ZipFile(io.BytesIO(archive.stdout)) as contents:
        contents.extractall(baseline)
    return baseline / "skills" / "sdd-spec"


def replace_once(path, old, new):
    data = path.read_bytes()
    if data.count(old) != 1:
        raise PilotFailure(f"fixture {path} should contain {old!r} exactly once")
    path.write_bytes(data.replace(old, new, 1))


def prepare_project(workspace, templates, scenario):
    project = workspace / scenario.id / "project with spaces"
    change = project / "sdd" / "changes" / CHANGE_ID
    for name in ("proposal.md", "design.md", "tasks.md", "spec.md"):
        directory = change / "specs" / "sample-capability" if name == "spec.md" else change
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes((templates / name).read_bytes())
    if scenario.edit == "missing_tasks":
        (change / "tasks.md").unlink()
    elif scenario.edit == "task_number":
        replace_once(change / "tasks.md", b"number: 1", b"number: 2")
    elif scenario.edit == "missing_proposal":
        (change / "proposal.md").unlink()
    elif scenario.edit == "proposal_version":
        replace_once(change / "proposal.md", b"schema_version: 1", b"schema_version: 99")
    elif scenario.edit == "proposal_encoding":
        (change / "proposal.md").write_bytes(b"\xff")
    return project, change


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_cli(repository, workspace, deadline):
    source = repository / "cli"
    # Identify the actual working sources, including changes awaiting a commit.
    files = [source / "go.mod", source / "go.sum", *source.rglob("*.go"),
             *(p for p in (source / "internal").rglob("*")
               if p.is_file() and p.suffix not in {".go"})]
    revision = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.relative_to(source).as_posix()):
        revision.update(path.relative_to(source).as_posix().encode() + b"\0")
        revision.update(bytes.fromhex(file_digest(path)))
    binary = workspace / ("sdd.exe" if os.name == "nt" else "sdd")
    command = ["go", "build", "-mod=readonly", "-o", str(binary), "./cmd/sdd"]
    built = run(command, source, deadline)
    if built.returncode:
        raise PilotFailure(f"{command!r} exited {built.returncode}: {built.stderr!r}")
    print(f"Go sources SHA-256 {revision.hexdigest()}", flush=True)
    print(f"Go binary {binary}\nGo binary SHA-256 {file_digest(binary)}", flush=True)
    return binary


def snapshot(root, deadline):
    entries = {}

    def visit(path):
        time_remaining(deadline)
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            entries[relative] = ("symlink", os.readlink(path))
        elif (getattr(metadata, "st_reparse_tag", None)
              == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)):
            entries[relative] = ("mount_point", os.readlink(path))
        elif stat.S_ISDIR(mode):
            entries[relative] = ("directory",)
            for child in path.iterdir():
                visit(child)
        elif stat.S_ISREG(mode):
            entries[relative] = ("file", file_digest(path))
        else:
            entries[relative] = ("mode", stat.S_IFMT(mode))

    try:
        visit(root)
    except FileNotFoundError as exc:
        if exc.filename is None or Path(exc.filename) != root:
            raise
    return entries


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"invalid JSON constant {value}")


def display(value):
    if value is MISSING:
        return "<missing>"
    if value is None or type(value) is bool:
        return json.dumps(value)
    return repr(value)


def equal(left, right, path, labels):
    if type(left) is type(right):
        if isinstance(left, dict):
            for key in sorted(left.keys() | right.keys()):
                escaped = key.replace("~", "~0").replace("/", "~1")
                equal(left.get(key, MISSING), right.get(key, MISSING), f"{path}/{escaped}", labels)
            return
        if isinstance(left, list):
            for index in range(max(len(left), len(right))):
                left_item = left[index] if index < len(left) else MISSING
                right_item = right[index] if index < len(right) else MISSING
                equal(left_item, right_item, f"{path}/{index}", labels)
            return
        if left == right:
            return
    raise PilotFailure(f"{path}: {labels[0]}={display(left)}, {labels[1]}={display(right)}")


def read_observation(label, command, cwd, project, deadline):
    try:
        before = snapshot(project, deadline)
        result = run(command, cwd, deadline)
        after = snapshot(project, deadline)
        for path in sorted(before.keys() | after.keys()):
            equal(before.get(path, MISSING), after.get(path, MISSING), f"/filesystem/{path}",
                  ("before", "after"))
        output = json.loads(result.stdout.decode("utf-8"), object_pairs_hook=unique_object,
                            parse_float=Decimal, parse_constant=invalid_constant)
    except TimeoutError:
        raise
    except OSError as exc:
        raise PilotFailure(f"{label} /process: {exc}") from exc
    except PilotFailure as exc:
        raise PilotFailure(f"{label} {exc}") from exc
    except (ValueError, ArithmeticError, RecursionError) as exc:
        raise PilotFailure(f"{label} /stdout: expected one UTF-8 JSON document ({exc}); "
                           f"exit={result.returncode}, stdout={result.stdout[:1000]!r}, "
                           f"stderr={result.stderr[:1000]!r}") from exc
    errors = output.get("errors") if isinstance(output, dict) else None
    if isinstance(errors, list):
        for index, issue in enumerate(errors):
            if isinstance(issue, dict) and issue.get("code") == "environment":
                raise PilotFailure(f"{label} /stdout/errors/{index}: {display(issue)}")
    return result, output


def check_expectation(scenario, change, result, output):
    labels = ("expected", "observed")
    equal(scenario.exit_code, result.returncode, "/exit", labels)
    if not isinstance(output, dict):
        raise PilotFailure(f"/stdout: expected a JSON object, observed {display(output)}")
    for key, value in {"schema_version": 2, "stage": scenario.stage,
                       "work_kind": "change", "change_id": CHANGE_ID}.items():
        equal(value, output.get(key, MISSING), f"/stdout/{key}", labels)
    errors = output.get("errors", MISSING)
    if scenario.exit_code == 0:
        equal([], errors, "/stdout/errors", labels)
        approval = output.get("approval_status")
        approved = approval.get("approved", MISSING) if isinstance(approval, dict) else MISSING
        equal(False, approved, "/stdout/approval_status/approved", labels)
        if scenario.stage == "plan":
            equal({"done": 0, "total": 1}, output.get("progress", MISSING), "/stdout/progress", labels)
            tasks = output.get("tasks")
            available = tasks.get("available_by_graph", MISSING) if isinstance(tasks, dict) else MISSING
            equal(["TASK-sample-result"], available, "/stdout/tasks/available_by_graph", labels)
        return

    if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
        raise PilotFailure(f"/stdout/errors/0: expected a diagnostic object, observed {display(errors)}")
    issue = errors[0]
    for key in ("code", "path", "element_id", "message"):
        if key not in issue:
            raise PilotFailure(f"/stdout/errors/0/{key}: expected a diagnostic field, observed <missing>")
    code, document, message = {
        "P04": ("unreadable_input", "tasks.md", os.strerror(errno.ENOENT)),
        "P05": ("task_numbers", "tasks.md", "1..N"),
        "P06": ("unreadable_input", "proposal.md", os.strerror(errno.ENOENT)),
        "P07": ("unsupported_version", "proposal.md", "schema version: 99"),
        "P08": ("unreadable_input", "proposal.md", "'utf-8' codec can't decode byte 0xff"),
    }[scenario.id]
    equal(code, issue["code"], "/stdout/errors/0/code", labels)
    equal(str(change / document), issue["path"], "/stdout/errors/0/path", labels)
    if not isinstance(issue["message"], str) or message not in issue["message"]:
        raise PilotFailure(f"/stdout/errors/0/message: expected text containing {message!r}, "
                           f"observed {display(issue['message'])}")


def compare_stdout(python, go):
    equal(python, go, "/stdout", ("Python", "Go"))


def compare_stderr(python, go):
    if python != go:
        offset = next((index for index, pair in enumerate(zip(python, go)) if pair[0] != pair[1]),
                      min(len(python), len(go)))
        raise PilotFailure(f"/stderr byte {offset}: Python={python[offset:offset + 32]!r}, "
                           f"Go={go[offset:offset + 32]!r}")


def run_scenario(scenario, project, change, cwd, commands, deadline):
    arguments = ["--project-root", str(project), "--change", CHANGE_ID, "--stage", scenario.stage]
    python_result, python = read_observation("Python", commands[0] + arguments, cwd, project, deadline)
    go_result, go = read_observation("Go", commands[1] + arguments, cwd, project, deadline)
    equal(python_result.returncode, go_result.returncode, "/exit", ("Python", "Go"))
    compare_stdout(python, go)
    compare_stderr(python_result.stderr, go_result.stderr)
    for label, result, output in (("Python", python_result, python), ("Go", go_result, go)):
        try:
            check_expectation(scenario, change, result, output)
        except PilotFailure as exc:
            raise PilotFailure(f"{label} {exc}") from exc
    return python


def check_comparator(plan):
    for replacement in (True, 0):
        altered = deepcopy(plan)
        altered["approval_status"]["approved"] = replacement
        try:
            compare_stdout(plan, altered)
        except PilotFailure as exc:
            if str(exc).startswith("/stdout/approval_status/approved: "):
                continue
            raise
        raise PilotFailure(f"comparator accepted approval_status.approved={display(replacement)}")


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=TIME_LIMIT)
    args = parser.parse_args()
    if not 0 < args.timeout <= TIME_LIMIT:
        parser.error(f"--timeout must be between 0 and {TIME_LIMIT} seconds")
    if not args.python.is_absolute() or not args.python.is_file():
        parser.error("--python must be the absolute path to the selected interpreter")
    basetemp = args.basetemp.resolve()
    if not basetemp.is_dir() or any((parent / ".git").exists() for parent in (basetemp, *basetemp.parents)):
        parser.error("--basetemp must be an existing directory outside Git worktrees")

    deadline = started + args.timeout
    try:
        print(f"Python commit {PYTHON_COMMIT}", flush=True)
        print(f"OS {platform.platform()}", flush=True)
        workspace = Path(tempfile.mkdtemp(prefix="sdd-pilot-", dir=basetemp))
        cwd = workspace / "caller"
        cwd.mkdir()
        print(f"Pilot workspace {workspace}", flush=True)
        repository = args.repository.resolve()
        baseline = prepare_baseline(repository, workspace, deadline)
        binary = build_cli(repository, workspace, deadline)
        # uv's environment setup messages would otherwise share the script's stderr pipe.
        commands = (["uv", "run", "--quiet", "--python", str(args.python), "--locked", "--script",
                     str(baseline / "scripts" / "check.py")], [str(binary), "check"])
        failed = False
        plan = None
        for scenario in SCENARIOS:
            project, change = prepare_project(workspace, baseline / "templates", scenario)
            arguments = f"--project-root {str(project)!r} --change {CHANGE_ID} --stage {scenario.stage}"
            try:
                output = run_scenario(scenario, project, change, cwd, commands, deadline)
            except TimeoutError as exc:
                raise PilotFailure(f"{scenario.id} {arguments}: {exc}") from exc
            except (PilotFailure, OSError) as exc:
                print(f"{scenario.id} FAIL {arguments}: {exc}", file=sys.stderr, flush=True)
                failed = True
            else:
                print(f"{scenario.id} PASS", flush=True)
                if scenario.id == "P02":
                    plan = output
        if plan is not None:
            check_comparator(plan)
            print("Comparator self-check PASS /stdout/approval_status/approved", flush=True)
        time_remaining(deadline)
    except (OSError, PilotFailure) as exc:
        print(f"Pilot failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Pilot elapsed {time.monotonic() - started:.2f} s", flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
