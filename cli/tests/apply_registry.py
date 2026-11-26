"""Compare an approved refactoring check revision and its acceptance (E08)."""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from pilot import PilotFailure, equal, run


TASK = "TASK-one"
CHECK = TASK + "/preserve-api"
CRITERION = "AC-preserved"
GROUP = "adapt-preservation-check"
REVISION = "revise-preservation-check"
ACCEPT = "accept-registry-revision"


def registry_cases(harness):
    """Both transition commands receive identical sealed inputs at one path."""
    project = harness.project
    change = project / "sdd" / "refactoring" / "registry-fixture"
    directory = change / "execution"
    path = directory / "state.json"
    arguments = {"directory": str(directory)}
    change.mkdir(parents=True)
    before_head = harness.git("rev-parse", "HEAD")
    tree = harness.git("rev-parse", "HEAD^{tree}")
    candidate = harness.git("commit-tree", tree, "-p", before_head, "-m", f"{TASK}: test registry confirmation")
    harness.git("update-ref", "HEAD", candidate, before_head)

    def fixture(phase):
        command = ["uv", "run", "--quiet", "--no-project", "--offline", "--python", str(harness.python),
                   "python", "-B", str(Path(__file__).resolve()), phase, str(harness.oracle_scripts), str(change)]
        result = run(command, harness.cwd, harness.deadline)
        if result.returncode or result.stderr:
            raise PilotFailure(f"E08 prepare {phase}: {result.stdout!r} {result.stderr!r}")

    def stored(ref):
        raw = (directory / ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"]
        return json.loads(raw)

    def registry(state):
        return stored(state["tasks"][TASK]["check_registry"]["$object"])

    def normalized_history(ref, timestamp):
        if ref is None:
            return None
        value = stored(ref)
        if "time" in value:
            datetime.fromisoformat(value["time"])
            if value["time"] == timestamp:
                value["time"] = "<current event timestamp>"
            value["previous"] = normalized_history(value["previous"], timestamp)
        elif "entry" in value:
            value["entry"] = normalized_history(value["entry"], timestamp)
        else:
            value["children"] = {key: normalized_history(child, timestamp) for key, child in value["children"].items()}
        return value

    def event(event_id, kind, payload, state, expected=0):
        base = path.read_bytes()
        request = {**arguments, "event": {"event_id": event_id, "run_id": state["run_id"],
                    "expected_revision": state["revision"], "type": kind, "task_id": TASK, "payload": payload}}
        observations = []
        for implementation in harness.commands:
            path.write_bytes(base)
            response = harness.process(implementation, "event", request, expected=expected)
            current = path.read_bytes()
            if expected:
                equal(current, base, f"/E08/{kind}/rejected-state", (implementation, "before"))
            state = json.loads(current)
            integrity = state.pop("integrity")
            canonical = json.dumps(state, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
            assert hashlib.sha256(canonical).hexdigest() == integrity
            timestamp = state.pop("updated_at")
            assert datetime.fromisoformat(timestamp).utcoffset().total_seconds() == 0
            if not expected:
                assert stored(state["event_head"])["time"] == timestamp
            for key in ("event_head", "event_index"):
                state[key] = normalized_history(state[key], timestamp)
            observations.append((response, state, registry(state)))
        equal(list(observations[0]), list(observations[1]), f"/E08/{kind}", ("Python", "Go"))
        return observations[1]

    try:
        fixture("prepare-revision")
        initial = json.loads(path.read_bytes())
        planned = registry(initial)
        before = planned["history"][-1]["checks"]
        after = deepcopy(before)
        after[0]["run"] = {"command": ["git", "rev-parse", "--verify", "HEAD"]}
        payload = {"registry_revision": 1, "before": before, "after": after,
                   "basis": {"test_changes": [GROUP]}, "preserves": [CRITERION],
                   "reason": "Adapt the exact revision check while preserving the API obligation",
                   "mapping": {CHECK: "The Git revision check switches to explicit verification"}}
        wrong_revision, _, _ = event("stale-registry", "checks_revise", {**payload, "registry_revision": 0}, initial, 1)
        assert wrong_revision["code"] == "registry_revision_conflict"
        wrong_mapping, _, _ = event("missing-mapping", "checks_revise", {**payload, "mapping": {}}, initial, 1)
        assert wrong_mapping["code"] == "revision_mapping"
        staged, advanced, pending = event(REVISION, "checks_revise", payload, initial)
        assert staged["result"]["event_result"] == {"registry_revision": 2, "status": "pending_confirmation", "checks": after}
        assert advanced["revision"] == initial["revision"] + 1 and advanced["tasks"][TASK]["status"] == "running"
        assert pending["confirmed_revision"] == 0 and pending["history"][0] == planned["history"][0]
        assert pending["transition"] == {"event_id": REVISION, **payload}
        assert pending["history"][-1]["transition"] == pending["transition"]

        fixture("prepare-acceptance")
        advanced = json.loads(path.read_bytes())
        accepted, finished, confirmed = event(ACCEPT, "accept", {}, advanced)
        assert accepted["result"]["event_result"] == {"status": "accepted", "sha": candidate}
        assert finished["tasks"][TASK]["status"] == "accepted"
        assert confirmed["confirmed_revision"] == pending["revision"]
        assert confirmed["confirmation_event"] == ACCEPT and confirmed["history"] == pending["history"]
    finally:
        harness.git("update-ref", "HEAD", before_head, candidate)
        if change.is_dir():
            destination = harness.workspace / "registry execution fixture"
            assert change.resolve().parents[2] == project.resolve() and destination.resolve().parent == harness.workspace.resolve()
            change.rename(destination)
    print("E08 PASS (pending revision, rejection and acceptance)", flush=True)


def prepare_revision(change):
    from lib.repository import repository
    from lib.state import initialize, save, seal, snapshot
    from lib.verification import record_registry

    project = change.parents[2]
    repo = repository(project)
    planned = {"id": TASK, "number": 1, "depends_on": [], "preserves": [CRITERION], "verification": [],
               "test_changes": [{"id": GROUP, "action": "adapt", "criteria": [CRITERION], "replacement_criteria": [CRITERION]}]}
    basis = {"schema_version": 2, "change_id": change.name, "work_kind": "refactoring", "head": repo.head(),
             "branch": repo.branch(), "project_root": str(project), "change_root": str(change), "tasks": [planned],
             "instruction": {"text": "Execute the registry fixture", "source": "test fixture"}, "acceptance": [], "verification": []}
    state = initialize(basis, isolation=True)
    task = state["tasks"][TASK]
    check = {"id": CHECK, "criteria": [CRITERION], "source": "tasks.md", "location": "check.py", "cwd": ".",
             "configuration": {}, "setup": None, "run": {"command": ["git", "rev-parse", "HEAD"]}}
    task.update(status="running", executor="executor", roles=["executor"], checks=[check], attempt=1,
                baseline_checks={"run_id": state["run_id"], "before": snapshot(state), "outputs": [{"outcome": "passed"}]})
    state["roles"]["executor"] = {"role_id": "executor", "kind": "executor", "task_id": TASK,
                                    "context_id": "original executor", "status": "active"}
    record_registry(state, task, {"event_id": "fixture-checks-request", "type": "checks_register"})
    save(change / "execution", seal(state))


def prepare_acceptance(change):
    from lib import check_evidence, verification_results
    from lib.check_registry import selected
    from lib.common import digest, write_json
    from lib.repository import repository
    from lib.state import read, save, seal, snapshot

    directory = change / "execution"
    state = read(directory)
    task = state["tasks"][TASK]
    source = snapshot(state)
    project = state["basis"]["project_root"]
    head = source["commit"]
    repo = repository(project)
    info = repo.commit_info(head)
    candidate = {"sha": head, "tree": info["tree"], "parent": info["parent"], "root": project}
    checks = selected(state, task)
    revision = task["check_registry"]["revision"]
    state["roles"]["executor"]["status"] = "finished"
    state["roles"]["verifier"] = {"role_id": "verifier", "kind": "explorer", "task_id": TASK, "status": "finished",
        "fresh": True, "registered_revision": state["revision"], "context_id": "independent verifier",
        "assignment": {"kind": "checks", "stage": "independent", "registry_revision": revision,
            "scope": {"project": project, "work": state["change_id"], "task": TASK}, "basis": {"checks": checks, "source": source, "run_id": state["run_id"]}}}
    task.update(status="committing", candidate_commit=candidate, commits=[candidate],
                worktree={"path": project, "integrated": True, "integration_tree": info["tree"]}, transfer={"snapshot": source},
                reviews=[{"round_id": "review-1", "lens_id": lens, "verdict": "pass", "findings": []}
                         for lens in ("verification", "code")])
    outputs = []
    for check in checks:
        # Produce actual command output. Only the host attestations and the
        # assembled acceptance checkpoint are pre-seeded for this timing budget.
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        process = subprocess.run(check["run"]["command"], cwd=project, capture_output=True, check=True, timeout=5, **options)
        outputs.append({"check_id": check["id"], "criteria": check["criteria"], "outcome": "passed", "exit_code": 0,
                        "stdout": process.stdout.decode(), "stderr": process.stderr.decode()})
    record = {"run_id": state["run_id"], "work_kind": "refactoring", "task_id": TASK, "role_id": "verifier",
              "stage": "independent", "before": source, "after": source, "registry_revision": revision,
              "registered_checks": checks, "outputs": outputs}
    check_evidence.persist(state, record, checks, directory, "registry-fixture-proof")
    relative = "evidence/registry-acceptance.json"
    write_json(directory / relative, record)
    log_hash = digest((directory / relative).read_bytes())
    task["evidence"] = [{"check_id": check["id"], "outcome": "passed", "head": head, "role_id": "verifier",
                         "stage": "independent", "log": relative, "log_hash": log_hash} for check in checks]
    state["roles"]["reviewer"] = {"role_id": "reviewer", "kind": "reviewer", "lens_id": "verification", "task_id": TASK,
                                   "status": "finished", "fresh": True, "context_id": "independent reviewer"}
    packet = verification_results.packet(state, task, directory, "independent")
    criteria = packet.pop("criteria")
    task["verification_results"] = [{**packet, "id": "fixture-verification-conclusion", "role_id": "reviewer",
        "round_id": "review-1", "time": state["updated_at"], "trace": "synthetic fixture attestation", "limitations": [],
        "outcome": "passed", "attempts_hash": digest(verification_results.attempts(task, "independent")),
        "criteria_results": [{"criterion_id": criterion, "outcome": "passed", "reason": "Inspect the matching command output",
                              "references": [relative]} for criterion in criteria]}]
    save(directory, seal(state))


if __name__ == "__main__":
    phase, scripts, root = sys.argv[1:]
    sys.path.insert(0, scripts)
    {"prepare-revision": prepare_revision, "prepare-acceptance": prepare_acceptance}[phase](Path(root).resolve())
