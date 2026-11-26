"""Compare the SDD spec and shared commands against the registry's pinned Python version."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pilot


def check_response(result, expected_exit, label):
    if result.returncode != expected_exit:
        raise AssertionError(f"{label}: expected exit {expected_exit}, got {result.returncode}: "
                             f"{result.stdout!r} {result.stderr!r}")
    return json.loads(result.stdout.decode("utf-8"), object_pairs_hook=pilot.unique_object)


def compare(label, left, right):
    pilot.equal(left, right, label, ("Python", "Go"))


def readonly(spec, workspace, binary, deadline):
    project = workspace / "role settings"
    project.mkdir()
    user_dir = workspace / "user catalog"
    user_dir.mkdir()

    def call(cmd, args, code, expect, fixture=None):
        name = {"resolve-agent": "resolve_agent.py", "simplicity": "simplicity.py", "check": "check.py"}[cmd]
        commands = [oracle(spec / "scripts" / name), [binary, cmd]]
        outputs = []
        for command in commands:
            process, output = pilot.read_observation(cmd, [*command, *args], workspace, fixture or project, deadline)
            check_response(process, code, cmd)
            if not expect(output):
                raise AssertionError(f"{cmd}: expected independent outcome, observed {output!r}")
            outputs.append((output, process.stderr))
        compare(cmd, outputs[0][0], outputs[1][0])
        pilot.compare_stderr(outputs[0][1], outputs[1][1])

    for case in pilot.SCENARIOS:
        fixture, change = pilot.prepare_project(workspace, spec / "templates", case)
        outcome = pilot.run_scenario(case, fixture, change, workspace,
                                    (oracle(spec / "scripts/check.py"), [binary, "check"]), deadline)
        if case.id == "P02":
            pilot.check_comparator(outcome)
    print("P01–P08 PASS", flush=True)

    fixture, change = pilot.prepare_project(workspace / "review [1]", spec / "templates", pilot.Scenario("D01", "plan", 0))
    templates = spec / "templates"
    ref = fixture / "sdd" / "refactoring" / pilot.CHANGE_ID
    ref.mkdir(parents=True)
    for name in ("proposal.md", "design.md", "tasks.md"):
        (ref / name).write_bytes((templates / ("refactoring-" + name)).read_bytes()
                                 .replace(b"sample-refactoring", pilot.CHANGE_ID.encode()))
    (fixture / "docs").mkdir()
    (fixture / "docs/contracts.md").write_text("# REQ-product-api\n")
    check = ["--project-root", fixture, "--change", pilot.CHANGE_ID, "--stage", "plan", "--work-kind"]
    call("check", [*check, "refactoring"], 0, lambda o: o["progress"]["total"] == 3, fixture)
    call("check", [*check, "change"], 0, lambda o: o["progress"]["total"] == 1, fixture)
    taskfile = change / "tasks.md"
    original = taskfile.read_bytes()
    pilot.replace_once(taskfile, b"depends_on: []", b"depends_on: [TASK-sample-result]")
    call("check", [*check, "change"], 1,
         lambda o: "task_cycle" in {e["code"] for e in o["errors"]}, fixture)
    taskfile.write_bytes(original)
    for name in ("state.yaml", "state.md"):
        (change / name).write_bytes((templates / name).read_bytes())
    (change / "review").mkdir()
    decision = {"sdd_record": "user", "id": "USER-approve", "kind": "document_approval",
                "change_id": pilot.CHANGE_ID, "work_kind": "change", "scope": {"stage":"review"},
                "response":"approved", "date":"2025-01-01T00:00:00Z", "basis_commit":"a" * 40}
    work = dict(decision, id="USER-planning", kind="planning_command", scope={"stage":"review","work":"draft"})
    raw = (templates / "decisions.md").read_bytes()
    for row in (decision, work):
        raw += ("\n### " + row["id"] + "\n\n```yaml\n" + json.dumps(row) + "\n```\n").encode()
    (change / "review/decisions.md").write_bytes(raw)
    run = change / "review/20260101T000000Z-example"
    run.mkdir()
    (run / "consistency.md").write_bytes((templates / "review-report.md").read_bytes())
    call("check", [*check, "change"], 0, lambda o: o["approval_status"]["ready"] is True
         and "USER-planning" in o["approval_status"]["work_authorizations"]
         and o["review_status"]["coverage"]["consistency"] == "incomplete", fixture)
    print("D01 PASS", flush=True)

    role = "sdd-spec.architect"
    common = ["--project-root", project, "--role", role]
    codex = [*common, "--host", "codex", "--user-agent-dir", user_dir]
    call("resolve-agent", [*codex, "--native-inheritance"], 0,
         lambda o: o["result"]["reason"] == "settings_missing")
    settings = project / ".sdd" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"schema_version": 1, "subagents": {"roles": {role: "design"}}}))
    (user_dir / "custom.toml").write_text('name = "design"\ndescription = "Design reviewer"\n'
                                        'developer_instructions = "Read the change."\nmodel = "model-one"\n')
    call("resolve-agent", [*codex, "--parent-model", "model-two", "--parent-effort", "high"],
         0, lambda o: o["result"]["launch"] == {"fork_turns": "none", "model": "model-one"})
    catalog = workspace / "available.json"
    claude = [*common, "--host", "claude-code", "--available-agents", catalog, "--native-inheritance"]
    for names, code, mode in [(["design"], 0, "native-agent"), (["general-purpose"], 0, "parent"), ([], 1, "")]:
        catalog.write_text(json.dumps(names))
        call("resolve-agent", claude, code, lambda o: o.get("result", {}).get("mode", "") == mode)
    print("D02 PASS", flush=True)
    for model, profile, code in [("gpt-6-astra", "gpt-6-astra", 0), ("claude-future", "claude", 0),
                                 ("other", None, 0), (None, None, 0), (" k3 ", None, 1)]:
        expected = f"references/simplicity-model-{profile}.md" if profile else None
        call("simplicity", [] if model is None else ["--model", model], code,
             lambda o: o.get("profile") == expected and o["ok"] == (code == 0))
    print("D03 PASS", flush=True)


def oracle(path):
    return ["uv", "run", "--quiet", "--python", sys.executable, "--locked", "--script", str(path)]


def checkpoints(shared, workspace, binary, deadline):
    # Both real indexes, refs, hooks and the worktree identity cross the process boundary.
    # Use the same path sequentially and a fixed Git identity/date so OIDs are comparable.
    os.environ.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                      GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                      GIT_AUTHOR_DATE="2025-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2025-01-01T00:00:00+00:00",
                      GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    project = workspace / "git project"
    instruction = workspace / "instruction.json"
    instruction.write_text('{"text":"Create work","source":"fixture"}')
    decision = workspace / "decision.json"
    changes = workspace / "changes.json"

    def workflow(command):
        project.mkdir()
        samples = []
        def git(*args):
            p = pilot.run(["git", "-C", project, *args], workspace, deadline)
            if p.returncode:
                raise AssertionError(f"git {args}: {p.stderr!r}")
            return p.stdout.decode().strip()
        def call(op, status, *extra, slug="sample-change"):
            args = [op, "--work-kind", "change", "--change", slug, "--project-root", project, *extra]
            p = pilot.run([*command, *args], workspace, deadline)
            code = int(status in {"changes_changed", "concurrent_change", "commit_created_unaccepted", "work_exists"})
            data = check_response(p, code, op)
            if data["status"] != status:
                raise AssertionError(f"{op}: expected {status}, got {data}")
            # Compare public results and durable Git state after every call, including rejected writes.
            samples.append([data, p.stderr.hex(), git("for-each-ref", "--format=%(refname) %(objectname)"),
                            git("status", "--porcelain=v1"), git("write-tree"),
                            git("log", "-1", "--format=%H %P %T")])
            return data
        git("init", "-q", "-b", "main")
        (project / "module.txt").write_bytes(b"start\n")
        git("add", "module.txt"); git("commit", "-qm", "base")
        head = git("rev-parse", "HEAD")
        call("inspect", "initialization_required", "--review-changes")
        occupied = project / "sdd" / "changes" / "occupied"
        occupied.mkdir(parents=True)
        call("inspect", "acceptance_required", slug="occupied")
        call("initialize", "work_exists", "--expected-head", head, "--instruction", instruction, slug="occupied")
        cp = call("initialize", "initialized", "--expected-head", head, "--instruction", instruction)
        git("worktree", "add", "-q", "--detach", str(workspace / "linked tree"), head)
        other = pilot.run([*command, "inspect", "--project-root", workspace / "linked tree", "--work-kind", "change",
                           "--change", "sample-change"], workspace, deadline)
        other_data = check_response(other, 0, "linked worktree")
        if cp["checkpoint_ref"] == other_data["checkpoint_ref"] or other_data["status"] != "acceptance_required":
            raise AssertionError(other_data)
        samples.append([other_data, other.stderr.hex()])
        git("worktree", "remove", str(workspace / "linked tree"))
        (project / "module.txt").write_bytes(b"independent\n")
        git("commit", "-qam", "new head")
        new = git("rev-parse", "HEAD")
        call("inspect", "head_mismatch")
        decision.write_text(json.dumps(dict(id="USER-yes", response="yes", source="test", date="2025-01-01",
                                            accepted_commit=new)))
        call("accept", "accepted", "--expected-head", new, "--expected-accepted", head, "--decision", decision)
        call("accept", "concurrent_change", "--expected-head", new, "--expected-accepted", head, "--decision", decision)
        (project / "module.txt").write_bytes(b"candidate\n")
        current = call("inspect", "dirty", "--review-changes")["reviewed_changes"]
        changes.write_text(json.dumps(current))
        args = ["--expected-head", new, "--expected-accepted", new, "--instruction", instruction,
                "--reviewed-changes", changes, "--message", "checkpoint"]
        git("add", "module.txt")
        call("create", "changes_changed", *args)
        current = call("inspect", "dirty", "--review-changes")["reviewed_changes"]
        changes.write_text(json.dumps(current))
        created = call("create", "created", *args)["created_commit"]
        current = call("inspect", "ready", "--review-changes")["reviewed_changes"]
        changes.write_text(json.dumps(current))
        args[1] = args[3] = created
        call("create", "unchanged", *args)
        # An external ref update between commit creation and CAS must leave the new commit visible.
        hook = project / ".git" / "hooks" / "post-commit"
        hook.write_bytes(f"#!/bin/sh\ngit update-ref {cp['checkpoint_ref']} {head}\n".encode())
        hook.chmod(0o755)
        (project / "module.txt").write_bytes(b"racing writer\n")
        current = call("inspect", "dirty", "--review-changes")["reviewed_changes"]
        changes.write_text(json.dumps(current))
        call("create", "commit_created_unaccepted", *args)
        return samples

    left = workflow(oracle(shared / "scripts" / "checkpoint.py"))
    project.rename(workspace / "finished oracle")
    right = workflow([binary, "checkpoint"])
    compare("D04-D07", left, right)
    print("D04 D05 D06 D07 PASS", flush=True)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("spec", "checkpoint"))
    parser.add_argument("--basetemp", required=True, type=Path)
    args = parser.parse_args()
    deadline = started + 118
    base = args.basetemp.resolve()
    if not base.is_dir() or any((p / ".git").exists() for p in (base, *base.parents)):
        parser.error("basetemp must be an existing external directory")
    workspace = Path(tempfile.mkdtemp(prefix="sdd-" + args.suite + "-", dir=base))
    repo = Path(__file__).resolve().parents[2]
    try:
        spec = pilot.prepare_baseline(repo, workspace, deadline)
        binary = pilot.build_cli(repo, workspace, deadline)
        if args.suite == "spec":
            readonly(spec, workspace, binary, deadline)
        else:
            checkpoints(spec.parent / "sdd-shared", workspace, binary, deadline)
    finally:
        print(f"{args.suite} elapsed {time.monotonic() - started:.2f} s; fixture {workspace}", flush=True)


if __name__ == "__main__":
    main()
