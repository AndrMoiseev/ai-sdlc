"""Compare native execution operations with the pinned Python CLI."""

import argparse
import compileall
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import urlopen

from pilot import (PYTHON_COMMIT, PilotFailure, build_cli, equal, prepare_baseline,
                   run, time_remaining)

BATCH_ENTRYPOINT = """
import contextlib
import io
import json
from pathlib import Path
import sys

entrypoint, batch, request = map(Path, sys.argv[1:])
sys.path.insert(0, str(entrypoint.parent))
sys.stdout.reconfigure(encoding="utf-8")
from execute import main

responses = []
for operation in json.loads(batch.read_bytes()):
    request.write_text(json.dumps(operation), encoding="utf-8")
    sys.argv = [str(entrypoint), "--request", str(request)]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main()
    responses.append((code, stdout.getvalue(), stderr.getvalue()))
print(json.dumps(responses))
"""


def document(path, metadata, records=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".yaml":
        path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return
    parts = ["---\n", json.dumps(metadata, indent=2), "\n---\n"]
    for record in records:
        parts.extend(("\n### Record\n\n```yaml\n", json.dumps(record, indent=2),
                      "\n```\n\nDescription.\n"))
    path.write_text("".join(parts), encoding="utf-8")


class ApplyHarness:
    def __init__(self, workspace, repository, python, deadline):
        self.workspace = workspace
        self.deadline = deadline
        self.python = python
        self.cwd = workspace / "caller outside project"
        self.cwd.mkdir()
        baseline = prepare_baseline(repository, workspace, deadline,
                                    ("sdd-spec", "sdd-shared", "sdd-apply"))
        self.oracle_scripts = baseline.parent / "sdd-apply" / "scripts"
        # Each event invokes the pinned executable in a fresh interpreter. Cache
        # its imports once in the extracted external fixture for the timed suite.
        for scripts in (self.oracle_scripts, baseline.parent / "sdd-shared" / "scripts"):
            if not compileall.compile_dir(scripts, quiet=2):
                raise PilotFailure(f"Cannot compile reference scripts in {scripts}")
        binary = build_cli(repository, workspace, deadline)
        self.commands = {
            "Python": self.oracle(self.oracle_scripts / "execute.py"),
            "Go": [str(binary), "apply"],
        }
        self.checkpoint = self.oracle(baseline.parent / "sdd-shared" / "scripts" / "checkpoint.py")
        self.request = workspace / "request.json"
        self.project = workspace / "project with spaces [1]"
        self.change = self.project / "sdd" / "changes" / "demo"
        self.execution = self.change / "execution"
        self.arguments = {"project_root": str(self.project), "change": "demo",
                          "instruction": {"text": "Implement the fixture", "source": "test fixture"}}

    def oracle(self, path):
        return ["uv", "run", "--quiet", "--python", str(self.python), "--locked", "--script", str(path)]

    def git(self, *args):
        result = run(["git", "-C", str(self.project), *args], self.cwd, self.deadline)
        if result.returncode:
            raise PilotFailure(f"Git {args!r}: {result.stderr!r}")
        return result.stdout.decode().strip()

    def fixture(self):
        metadata = {"schema_version": 1, "change_id": "demo", "language": "en"}
        verification = [{"criteria": ["AC-one"], "test_description": "Check result",
                         "location": "check.py", "run": {"command": ["git", "rev-parse", "HEAD"]}}]
        tasks = [{"sdd_record": "task", "id": "TASK-one", "number": 1, "covers": ["AC-one"],
                  "depends_on": [], "status": "pending", "verification": verification},
                 {"sdd_record": "task", "id": "TASK-two", "number": 2, "covers": ["AC-two"],
                  "depends_on": ["TASK-one"], "status": "pending",
                  "verification": [{**verification[0], "criteria": ["AC-two"]}]}]
        for name in ("proposal", "design", "tasks"):
            document(self.change / f"{name}.md", {**metadata, "document_type": name},
                     tasks if name == "tasks" else ())
        document(self.change / "specs" / "demo" / "spec.md",
                 {**metadata, "document_type": "spec", "capability": "demo"},
                 [{"sdd_record": "requirement", "id": "REQ-one", "operation": "add"},
                  {"sdd_record": "acceptance", "id": "AC-one", "requirement": "REQ-one",
                   "conditions": "Fixture", "expected": "Result"},
                  {"sdd_record": "acceptance", "id": "AC-two", "requirement": "REQ-one",
                   "conditions": "Follow-up", "expected": "Follow-up result"}])
        record = {"sdd_record": "user", "id": "USER-approve", "kind": "document_approval",
                  "work_kind": "change", "change_id": "demo", "scope": {"stage": "review"},
                  "response": "Approved fixture", "date": "2026-10-08T00:00:00Z", "basis_commit": "a" * 40}
        document(self.change / "review" / "decisions.md",
                 {"schema_version": 2, "document_type": "decisions", "work_kind": "change", "change_id": "demo"},
                 [record])
        state = {**metadata, "schema_version": 2, "document_type": "state", "work_kind": "change",
                 "phase": "approved", "awaiting": "none", "flow": "plan", "next_question": None,
                 "updated_at": "2026-10-08T00:00:00Z", "document_links": ["tasks.md"],
                 "review_links": ["review/decisions.md"], "approval_refs": [record["id"]],
                 "checks": {"structure": "passed"}}
        document(self.change / "state.yaml", state)
        (self.change / "state.md").write_text("# Continue the approved plan\n", encoding="utf-8")
        (self.project / "check.py").write_text("assert 2 + 3 == 5\n", encoding="utf-8")
        self.git("init", "-b", "main", "--template=")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.project / ".gitignore").write_text("/sdd/changes/demo/execution/\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "Fixture")
        args = ["inspect", "--project-root", str(self.project), "--change", "demo", "--work-kind", "change"]
        result = run(self.checkpoint + args, self.cwd, self.deadline)
        report = json.loads(result.stdout)
        self.git("update-ref", report["checkpoint_ref"], report["head"])
        return self.arguments

    def request_command(self, implementation, operation, args):
        self.request.write_text(json.dumps({"operation": operation, "args": args}), encoding="utf-8")
        return self.commands[implementation] + ["--request", str(self.request)]

    def process(self, implementation, operation, args=None, expected=0):
        command = self.request_command(implementation, operation, args or {})
        return self.observe(implementation, command, expected)

    def observe(self, implementation, command, expected):
        result = run(command, self.cwd, self.deadline)
        return self.response(implementation, result.returncode, result.stdout, result.stderr, expected)

    def response(self, implementation, code, stdout, stderr, expected):
        try:
            response = json.loads(stdout)
        except (ValueError, UnicodeError) as exc:
            raise PilotFailure(f"{implementation} returned invalid stdout: {stdout!r}; stderr={stderr!r}") from exc
        if code != expected or response["ok"] is not (expected == 0) or stderr:
            raise PilotFailure(f"{implementation} exited {code}: {response!r}, stderr={stderr!r}; expected {expected}")
        return response

    def compare(self, operation, args=None, expected=0):
        left, right = (self.process(kind, operation, args, expected) for kind in self.commands)
        equal(left, right, "/stdout", ("Python", "Go"))
        return right.get("result", right)

    def compare_batch(self, cases):
        # Exercise the unmodified entry point for every variant. Its argument
        # parser, JSON input, response envelope and exit code are all observed
        # separately. Sharing interpreter startup does not combine requests.
        original = self.oracle_scripts / "execute.py"
        wrapper = self.workspace / "apply oracle batch.py"
        if not wrapper.exists():
            metadata = original.read_text(encoding="utf-8").partition('"""')[0]
            wrapper.write_text(metadata + BATCH_ENTRYPOINT, encoding="utf-8")
            shutil.copyfile(original.with_suffix(".py.lock"), wrapper.with_suffix(".py.lock"))
        batch = self.workspace / "apply oracle requests.json"
        batch.write_text(json.dumps([{"operation": operation, "args": args}
                                     for operation, args, _ in cases]), encoding="utf-8")
        result = run(self.oracle(wrapper) + [str(original), str(batch), str(self.request)], self.cwd, self.deadline)
        if result.returncode or result.stderr:
            raise PilotFailure(f"Pinned batch failed with exit {result.returncode}: {result.stderr!r}")
        outputs = []
        for (operation, args, expected), (code, stdout, stderr) in zip(cases, json.loads(result.stdout), strict=True):
            left = self.response(f"Python {operation}", code, stdout, stderr, expected)
            right = self.process("Go", operation, args, expected)
            equal(left, right, f"/{operation}/stdout", ("Python", "Go"))
            outputs.append(right.get("result", right))
        return outputs

    def initialized(self, implementation="Python"):
        return self.process(implementation, "initialize", {**self.arguments, "isolation": True})["result"]

    def event(self, implementation, state, kind, payload, task_id="TASK-one", event_id=None, expected=0):
        event = {"event_id": event_id or kind + "-" + str(state["revision"]), "run_id": state["run_id"],
                 "expected_revision": state["revision"], "type": kind, "task_id": task_id, "payload": payload}
        args = {"directory": str(self.execution), "event": event}
        return self.process(implementation, "event", args, expected)

    def state(self, implementation="Python", view="full"):
        return self.process(implementation, "read", {"directory": str(self.execution), "view": view})["result"]


def read_views(harness):
    directory = str(harness.execution)
    args = {"directory": directory}
    saved = json.loads((harness.execution / "state.json").read_bytes())
    reference = saved["baseline"]["$object"]
    nested = {"source": {"$object": reference}}
    encoded = json.dumps(nested, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = f"objects/{digest[:2]}/{digest}.json"
    stored = harness.execution / path
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(encoded)
    wrapper = {"path": path, "sha256": digest, "bytes": len(encoded), "kind": "object"}
    compact, explicit, state, source, encoded_object, audit, available = harness.compare_batch([
        ("read", args, 0),
        ("read", {**args, "view": "compact"}, 0),
        ("read", {**args, "view": "full"}, 0),
        ("read_object", {**args, "reference": reference}, 0),
        ("read_object", {**args, "reference": wrapper}, 0),
        ("audit", args, 0),
        ("available", args, 0),
    ])
    assert compact == explicit and compact["view"] == "compact" and compact["available_tasks"] == ["TASK-one"]
    assert state == saved and state["revision"] == 0
    print("O04 PASS", flush=True)
    assert source["commit"] == state["basis"]["head"] and encoded_object == nested
    print("O05 read PASS", flush=True)
    assert audit["events"] == 0 and audit["status"] == "verified"
    assert available == ["TASK-one"]
    print("O08 PASS", flush=True)
    return state, args, wrapper


def compare_dashboard(harness, arguments):
    names = ("dashboard.html", "dashboard-state.js", "summary.md", "technical-debt.md")
    rendered = harness.process("Python", "dashboard", arguments)
    expected = {name: (harness.execution / name).read_bytes() for name in names}
    for name in names:
        (harness.execution / name).unlink()
    equal(rendered, harness.process("Go", "dashboard", arguments), "/dashboard/stdout", ("Python", "Go"))
    for name, value in expected.items():
        if (harness.execution / name).read_bytes() != value:
            raise PilotFailure(f"O10 artifact {name} differs from Python")


def help_cases(harness):
    index = harness.compare("help")
    assert len(index["operations"]) == 13 and len(index["events"]) == 29
    # Enumerate the pinned catalogue in one process. The file and flag
    # selectors delegate to this same function in the Python entry point.
    code = """
import json, sys
sys.path.insert(0, sys.argv[1])
from lib.api_help import describe
names = describe()
print(json.dumps({"index": names, **{
    key + "s": {name: describe(**{key: name}) for name in names[key + "s"]}
    for key in ("operation", "event")
}}))
"""
    expected = run([str(harness.python), "-B", "-c", code, str(harness.oracle_scripts)],
                   harness.cwd, harness.deadline)
    if expected.returncode or expected.stderr:
        raise PilotFailure(f"Pinned help catalogue failed: {expected.stderr!r}")
    catalogue = json.loads(expected.stdout)
    for selector in ("operation", "event"):
        for name, contract in catalogue[selector + "s"].items():
            got = harness.process("Go", "help", {selector: name})["result"]
            equal(contract, got, f"/help/{selector}/{name}", ("Python", "Go JSON"))
            via_flag = harness.observe("Go", [*harness.commands["Go"], f"--help-{selector}", name], 0)
            equal(contract, via_flag["result"], f"/help/{selector}/{name}", ("Python", "Go flag"))
    for flags in (["--help-operation"], ["--help-operation", "event"], ["--help-event", "block"]):
        for kind, command in harness.commands.items():
            result = harness.observe(kind, command + flags, 0)
            expected = index
            if len(flags) == 2:
                selector = flags[0].removeprefix("--help-")
                expected = catalogue[selector + "s"][flags[1]]
            equal(result["result"], expected, f"/help/{' '.join(flags)}", ("argument", "request"))
    harness.compare("help", {"event": "no-such-event"}, 1)
    print("O01 PASS", flush=True)


def initialize_cases(harness):
    harness.fixture()
    instruction = {**harness.arguments, "instruction": None}
    other = harness.project / "sdd" / "refactoring" / "demo"
    other.mkdir(parents=True)
    basis, missing, ambiguous = harness.compare_batch([
        ("validate", harness.arguments, 0),
        ("validate", instruction, 1),
        ("validate", {**harness.arguments, "work_kind": None}, 1),
    ])
    other.rmdir()
    assert basis["work_kind"] == "change"
    assert [task["id"] for task in basis["tasks"]] == ["TASK-one", "TASK-two"]
    assert missing["code"] == "execution_instruction" and ambiguous["code"] == "ambiguous_change"
    decisions = harness.change / "review" / "decisions.md"
    checkpoint = harness.change / "state.yaml"
    original_decisions, original_checkpoint = decisions.read_bytes(), checkpoint.read_bytes()
    try:
        document(decisions, {"schema_version": 2, "document_type": "decisions", "work_kind": "change", "change_id": "demo"})
        document(checkpoint, {**json.loads(original_checkpoint), "approval_refs": []})
        assert harness.compare("validate", harness.arguments, 1)["code"] == "approval_missing"
    finally:
        decisions.write_bytes(original_decisions)
        checkpoint.write_bytes(original_checkpoint)
    assert not harness.execution.exists()
    print("O02 PASS", flush=True)
    assert harness.compare("initialize", harness.arguments, 1)["code"] == "isolation_required"
    python = harness.initialized("Python")
    preserved = harness.workspace / "original execution"
    harness.execution.rename(preserved)
    go = harness.initialized("Go")
    for key in ("run_id", "updated_at"):
        assert python[key] != go[key]
        if key == "updated_at":
            datetime.fromisoformat(python[key])
            datetime.fromisoformat(go[key])
    dynamic = {"run_id", "updated_at", "integrity"}
    equal({k: v for k, v in python.items() if k not in dynamic},
          {k: v for k, v in go.items() if k not in dynamic}, "/O03/state", ("Python", "Go"))
    for name in ("dashboard.html", "dashboard-state.js", "summary.md", "technical-debt.md"):
        expected = (preserved / name).read_bytes()
        for key in ("run_id", "updated_at"):
            expected = expected.replace(python[key].encode(), go[key].encode())
        equal(expected, (harness.execution / name).read_bytes(), f"/O03/{name}", ("Python", "Go"))
    other = harness.workspace / "native execution"
    harness.execution.rename(other)
    preserved.rename(harness.execution)
    assert harness.compare("initialize", {**harness.arguments, "isolation": True}, 1)["code"] == "already_started"
    print("O03 PASS", flush=True)


def worktree_and_resolver(harness, state, arguments):
    initial = harness.execution / "state.json"
    original = initial.read_bytes()
    event_id = "create-task-worktree"
    payload = {"workspace": str(harness.workspace / "isolated worktrees"), "resources": ["fixture-port"]}
    receipt = harness.execution / "runs" / state["run_id"] / "effects" / f"{event_id}.json"
    # The lifecycle covers a fresh creation through both implementations. Here
    # use one real worktree to exercise the original-root resolver and replay.
    created = harness.event("Go", state, "worktree_create", payload, event_id=event_id)
    worktree = created["result"]["event_result"]
    path = Path(worktree["path"])
    assert harness.git("-C", str(path), "rev-parse", "HEAD") == state["basis"]["head"]
    accepted = initial.read_bytes()
    assert json.loads(accepted)["revision"] == 1
    original_receipt = receipt.read_bytes()
    git_before = harness.git("worktree", "list", "--porcelain")
    for name in harness.commands:
        equal(created, harness.event(name, state, "worktree_create", payload, event_id=event_id),
              "/O09/replay-worktree", ("created", name))
    assert initial.read_bytes() == accepted and receipt.read_bytes() == original_receipt
    assert harness.git("worktree", "list", "--porcelain") == git_before
    settings = harness.project / ".sdd" / "settings.json"
    profile = harness.project / ".codex" / "agents" / "fixture-executor.toml"
    settings.parent.mkdir()
    profile.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"schema_version": 1, "subagents": {"roles": {"sdd-apply.executor": "fixture-executor"}}}), encoding="utf-8")
    profile.write_text('name = "fixture-executor"\ndescription = "Fixture"\nmodel = "gpt-fixture"\ndeveloper_instructions = "Fixture"\n', encoding="utf-8")
    cwd = harness.cwd
    try:
        harness.cwd = path
        role = {"kind": "executor", "host": "codex", "parent_model": "gpt-test",
                "user_agent_dir": str(harness.workspace / "empty user agents")}
        selected = harness.compare("resolve_agent", {**arguments, **role})
        assert selected["launch"]["model"] == "gpt-fixture"
        assert selected["settings"]["path"] == str(settings)
    finally:
        harness.cwd = cwd
        settings.unlink()
        profile.unlink()
    harness.git("worktree", "remove", str(path))
    harness.git("branch", "-D", worktree["branch"])
    receipt.unlink()
    initial.write_bytes(original)
    print("O07 and O09 Git replay PASS", flush=True)


def lock_cases(harness):
    path = harness.execution / "state.lock"
    args = {"directory": str(harness.execution)}
    owner = {"host": socket.gethostname(), "pid": os.getpid(), "token": secrets.token_hex(16)}
    path.write_text(json.dumps(owner), encoding="utf-8")
    assert harness.compare("recover_lock", args, 1)["message"] == "lock_owner_alive"
    assert path.exists()
    process = subprocess.Popen(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    process.wait(timeout=time_remaining(harness.deadline))
    owner["pid"] = process.pid
    # Release the Windows process handle so the second invocation observes an
    # absent PID. A retained handle keeps the exited process queryable.
    del process
    observations = []
    for kind in harness.commands:
        path.write_text(json.dumps(owner), encoding="utf-8")
        observations.append(harness.process(kind, "recover_lock", args))
        assert not path.exists()
    equal(*observations, "/O11", ("Python", "Go"))
    print("O11 PASS", flush=True)


def serve_one(harness, implementation):
    args = {"directory": str(harness.execution)}
    command = harness.request_command(implementation, "serve", {**args, "port": 0})
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True})
    with subprocess.Popen(command, cwd=harness.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options) as server:
        try:
            first_line = queue.Queue()
            threading.Thread(target=lambda: first_line.put(server.stdout.readline()), daemon=True).start()
            ready = json.loads(first_line.get(timeout=time_remaining(harness.deadline)))
            meta_path = harness.execution / "server.json"
            meta = json.loads(meta_path.read_bytes())
            assert ready == {"url": meta["url"], "run_id": meta["run_id"]}, f"{implementation}: metadata differs from handshake"
            assert ready["url"].startswith("http://127.0.0.1:"), f"{implementation}: dashboard missed loopback"
            with urlopen(ready["url"] + "/summary.md", timeout=time_remaining(harness.deadline)) as response:
                served = (response.status, response.headers["Content-Type"], response.headers["Cache-Control"], response.read())
            assert served[3] == (harness.execution / "summary.md").read_bytes(), f"{implementation}: served summary differs from disk"
            try:
                urlopen(ready["url"] + "/state.json", timeout=time_remaining(harness.deadline))
            except HTTPError as error:
                missing = error.code, error.read()
            else:
                raise PilotFailure("O12 exposed state.json")
            meta_path.write_text(json.dumps({**meta, "run_id": "unrelated"}), encoding="utf-8")
            wrong = harness.process(implementation, "stop_server", args, 1)
            assert wrong["code"] == "server_owner" and server.poll() is None, f"{implementation}: invalid owner stopped server"
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            stopped = harness.process(implementation, "stop_server", args)
            stdout, stderr = server.communicate(timeout=time_remaining(harness.deadline))
            assert stopped["result"]["stopped"] is True and not stderr and server.returncode == 0, f"{implementation}: shutdown failed"
            completion = json.loads(stdout)
            assert completion == {"ok": True, "result": {"stopped": ready["run_id"]}}, f"{implementation}: invalid completion {completion!r}"
            return served, missing, wrong, completion
        finally:
            if server.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True, timeout=3, **options)
                else:
                    os.killpg(server.pid, signal.SIGKILL)
                if server.poll() is None:
                    server.kill()


def event_and_history(harness, state, args, wrapper):
    path = harness.execution / "state.json"
    before = path.read_bytes()
    payload = {"reason": "Fixture blocker", "resume_condition": "Fixture resolution"}
    python = harness.event("Python", state, "block", payload)
    expected = json.loads(path.read_bytes())
    views = {name: (harness.execution / name).read_bytes()
             for name in ("summary.md", "dashboard-state.js", "dashboard.html", "technical-debt.md")}
    path.write_bytes(before)
    go = harness.event("Go", state, "block", payload)
    current = json.loads(path.read_bytes())
    equal(python, go, "/O09", ("Python", "Go"))
    assert current["revision"] == 1
    for name, content in views.items():
        equal(content.replace(expected["updated_at"].encode(), current["updated_at"].encode()),
              (harness.execution / name).read_bytes(), f"/O10/{name}", ("Python", "Go"))
    event = {"event_id": "block-0", "type": "block", "run_id": state["run_id"],
             "expected_revision": 0, "task_id": "TASK-one", "payload": payload}
    changed = {**event, "payload": {**payload, "reason": "changed"}}
    rejected, stale = harness.compare_batch([
        ("event", {**args, "event": changed}, 1),
        ("event", {**args, "event": {**event, "event_id": "new"}}, 1),
    ])
    assert rejected["code"] == "event_conflict" and stale["code"] == "revision_conflict"
    assert json.loads(path.read_bytes()) == current
    print("O09 PASS", flush=True)
    corrupt_directory = harness.execution / "dashboard.html"
    corrupt_directory.unlink()
    corrupt_directory.mkdir()
    extension = {"budget": "review", "limit": 4, "source": "fixture", "text": "Extend review"}
    result = harness.event("Go", current, "budget_extend", extension)
    assert "view_error" in result["result"] and result["ok"] is True
    corrupt_directory.rmdir()
    committed = path.read_bytes()
    assert json.loads(committed)["revision"] == 2
    compare_dashboard(harness, args)
    assert path.read_bytes() == committed
    print("O10 PASS", flush=True)
    index = json.loads(committed)["event_index"]
    assert harness.compare("audit", args)["events"] == 2
    object_path, index_path = (harness.execution / ref["path"] for ref in (wrapper, index))
    original_object, original_index = object_path.read_bytes(), index_path.read_bytes()
    object_path.write_bytes(b"changed")
    index_path.write_bytes(b"changed")
    try:
        object_error, index_error = harness.compare_batch([
            ("read_object", {**args, "reference": wrapper}, 1),
            ("audit", args, 1),
        ])
        assert object_error == {"ok": False, "code": "object_corrupt", "message": wrapper["path"]}
        assert index_error == {"ok": False, "code": "object_corrupt", "message": index["path"]}
    finally:
        object_path.write_bytes(original_object)
        index_path.write_bytes(original_index)
    print("O05 integrity PASS", flush=True)
    print("O06 PASS", flush=True)


def run_operations(harness, after_initialize=None):
    started = time.monotonic()
    initialize_cases(harness)
    state, arguments, wrapper = read_views(harness)
    if after_initialize is not None:
        after_initialize(harness, state)
    worktree_and_resolver(harness, state, arguments)
    event_and_history(harness, state, arguments, wrapper)
    lock_cases(harness)
    left, right = (serve_one(harness, kind) for kind in harness.commands)
    equal(left[0][0], right[0][0], "/O12/get/status", ("Python", "Go"))
    equal(left[0][1:3], right[0][1:3], "/O12/get/headers", ("Python", "Go"))
    equal(left[0][3], right[0][3], "/O12/get/body", ("Python", "Go"))
    equal(left[1][0], right[1][0], "/O12/missing/status", ("Python", "Go"))
    # The pinned script delegates error-page decoration to each interpreter's
    # standard library. Assert the HTTP error and visible diagnostic.
    for response in (left[1][1], right[1][1]):
        assert b"<p>Error code: 404</p>" in response, "O12 missing-resource error body"
    equal(left[2], right[2], "/O13/foreign-run", ("Python", "Go"))
    equal(left[3], right[3], "/O13/stopped", ("Python", "Go"))
    print("O12 O13 PASS", flush=True)
    help_cases(harness)
    print(f"Apply operations elapsed {time.monotonic() - started:.2f} s", flush=True)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=118)
    parser.add_argument("--operations-only", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 120 or not args.python.is_absolute():
        parser.error("Use an absolute interpreter and a timeout between 0 and 120 seconds")
    base = args.basetemp.resolve()
    if not base.is_dir() or any((parent / ".git").exists() for parent in (base, *base.parents)):
        parser.error("Use an existing temporary directory outside Git worktrees")
    workspace = Path(tempfile.mkdtemp(prefix="sdd-apply-cli-", dir=base))
    print(f"Apply workspace {workspace}\nPython commit {PYTHON_COMMIT}", flush=True)
    try:
        os.environ.update(GIT_AUTHOR_DATE="2025-01-01T00:00:00Z", GIT_COMMITTER_DATE="2025-01-01T00:00:00Z",
                          GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(workspace / "empty-git-config"))
        # Git for Windows ships both a launcher and the actual git executable.
        # Use the latter for the hundreds of real Git reads in these scenarios.
        if os.name == "nt" and shutil.which("git"):
            launcher = Path(shutil.which("git"))
            native = launcher.parent.parent / "mingw64" / "bin"
            if launcher.parent.name.lower() == "cmd" and (native / "git.exe").is_file():
                os.environ["PATH"] = str(native) + os.pathsep + os.environ["PATH"]
        harness = ApplyHarness(workspace, args.repository, args.python, started + args.timeout)
        if args.operations_only:
            run_operations(harness)
        else:
            from apply_events import compare_lifecycle
            from apply_registry import registry_cases
            seed = workspace / "initialized"
            def capture(h, _state):
                shutil.copytree(h.project, seed)
            run_operations(harness, capture)
            registry_cases(harness)
            compare_lifecycle(harness, seed, refresh=True)
        time_remaining(harness.deadline)
    except (AssertionError, PilotFailure, OSError, TimeoutError, ValueError, queue.Empty) as exc:
        print(f"Apply parity failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Apply elapsed {time.monotonic() - started:.2f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
