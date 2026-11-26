"""Exercise real execution events with synthetic host attestations and compare their public effects."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from apply import ApplyHarness, document
import pilot


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class Driver:
    """Read packed artifacts independently so an invalid object reference fails the test."""
    def __init__(self, harness, implementation):
        self.h = harness
        self.implementation = implementation
        self.trace = []
        self._verified = {}
        self._state = None
        self._manifest = None
        self._prefix = ""
        self.run_ids = []

    def read_ref(self, ref):
        sha = ref["sha256"]
        assert ref["path"] == f"objects/{sha[:2]}/{sha}.json"
        if sha in self._verified:
            prior, value = self._verified[sha]
            assert prior == ref
            return value
        raw = (self.h.execution / ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"] and digest(raw) == sha
        v = json.loads(raw)
        assert isinstance(v, {"object": dict, "array": list, "string": str}[ref["kind"]])
        self._verified[sha] = (ref, v)
        return v

    def expand(self, value):
        if isinstance(value, dict):
            if value.keys() == {"$object"}:
                return self.expand(self.read_ref(value["$object"]))
            return {k: self.expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.expand(v) for v in value]
        return value

    @property
    def state(self):
        raw = (self.h.execution / "state.json").read_bytes()
        if self._manifest == raw:
            return self._state
        m = json.loads(raw)
        assert m["integrity"] == digest({k: v for k, v in m.items() if k != "integrity"})
        self._state = self.expand(m)
        self._manifest = raw
        return self._state

    @property
    def task(self):
        return self.state["tasks"]["TASK-one"]

    @property
    def root(self):
        tree = self.task["worktree"]
        return Path(tree["path"]) if tree and not tree["integrated"] else self.h.project

    def comparable(self, value):
        if isinstance(value, list):
            return [self.comparable(v) for v in value]
        if not isinstance(value, dict):
            return value
        if value.keys() == {"path", "bytes", "kind", "sha256"}:
            return {"verified_object": self.comparable(self.expand(self.read_ref(value)))}
        result = {}
        for k, v in value.items():
            if k in ("time", "registered_at", "started_at", "updated_at", "finished_at") and isinstance(v, str):
                assert datetime.fromisoformat(v).tzinfo is not None
                v = "<timestamp>"
            elif k in ("duration_seconds", "remaining_timeout", "started", "expires") and isinstance(v, (int, float)):
                assert v >= 0
                v = "<seconds>"
            elif k in ("sha256", "log_hash", "procedure_log_hash") and ("log" in value or "procedure_log" in value):
                rel = value.get("procedure_log") if k == "procedure_log_hash" else value.get("log")
                if rel:
                    raw = (self.h.execution / rel).read_bytes()
                    assert digest(raw) == v
                    v = self.comparable(self.expand(json.loads(raw)))
            elif k == "attempts_hash":
                # Its assignment is checked by the following review_result/commit against live evidence.
                assert isinstance(v, str) and len(v) == 64
                v = "<attempts digest>"
            result[k] = self.comparable(v) if isinstance(v, (list, dict)) and not (k in ("sha256","log_hash","procedure_log_hash") and ("log" in value or "procedure_log" in value)) else v
        return result

    def send(self, kind, payload=None, task_id="TASK-one", error=None):
        before = json.loads((self.h.execution / "state.json").read_bytes())
        event_id = self._prefix + kind + "-" + str(before["revision"])
        response = self.h.event(self.implementation, before, kind, payload or {}, task_id, event_id=event_id,
                                expected=int(error is not None))
        after = json.loads((self.h.execution / "state.json").read_bytes())
        if error is not None:
            assert response["code"] == error, (kind, response)
            assert before == after
            self.trace.append([kind, response])
            return response
        assert after["revision"] == before["revision"] + 1
        result = self.expand(response["result"]["event_result"])
        self.trace.append([kind, self.comparable(result)])
        return result

    @contextmanager
    def branch(self, label):
        # Probe state transitions with a shared immutable object store. Isolate event
        # IDs and restore the manifest. Only use this for events without Git writes.
        path = self.h.execution / "state.json"
        saved = path.read_bytes()
        prefix = self._prefix
        self._prefix = label + "-"
        try:
            yield
        finally:
            path.write_bytes(saved)
            self._prefix = prefix

    def role(self, ident, kind, **extra):
        return self.send("role_register", {"role_id": ident, "kind": kind, "context_id": ident,
                         "fresh": True, "host": "codex", "launch_ref": "parity-fixture",
                         "capabilities": {"fresh_context": True}, **extra})

    def source(self, state):
        relative = self.h.change.relative_to(self.h.project)
        root = self.root
        files = {}
        for directory, children, names in os.walk(root / relative):
            if Path(directory) == root / relative and "execution" in children:
                children.remove("execution")
            for name in names:
                path = Path(directory) / name
                files[path.relative_to(root).as_posix()] = {"sha256": digest(path.read_bytes())}
        def git(*args):
            return self.h.git("-C", str(root), *args)
        return {"files": files, "digest": digest(files), "commit": git("rev-parse", "HEAD"),
                "branch": git("branch", "--show-current"), "dirty_paths": []}

    def explorer(self, stage):
        state = self.state
        task = state["tasks"]["TASK-one"]
        ident = f"{stage}-{state['revision']}"
        paths = sorted(["design.md", "proposal.md", "tasks.md", "specs/demo/spec.md"])
        basis = {"run_id": state["run_id"], "change_id": state["change_id"], "source": self.source(state),
                 "manifest": digest({"head": state["basis"]["head"], "document_paths": paths}),
                 "registry_revision": task["check_registry"]["revision"], "checks": task["checks"]}
        assignment = {"id": ident, "kind": "checks", "stage": stage, "basis": basis,
                      "scope": {"project": str(self.h.project), "work": "demo", "task":"TASK-one"},
                      "read_scope": ["project"], "outputs": [str(self.h.execution)], "limits": {"timeout": 90},
                      "registry_revision": basis["registry_revision"], "check_ids": [c["id"] for c in task["checks"]]}
        self.role(ident, "explorer", assignment=assignment, capabilities={"fresh_context":True,
                  "observations":{k:{"available":True, "trace":"fixture"} for k in
                                  ("launch","read","write_artifacts","run_command")}})
        return ident

    def stop(self, ident):
        return self.send("role_result", {"role_id":ident, "result":"DONE", "trace":"fixture"})

    def run_checks(self, stage, repeat=False):
        ident = self.explorer(stage)
        p = {"stage":stage, "role_id":ident}
        for check in self.task["checks"]:
            if "procedure" in check["run"] and not check["setup"]:
                proc = {**p,"check_id":check["id"]}
                if stage == "baseline" and check["id"] == "inspection":
                    with self.branch("expired"):
                        self.send("procedure_begin", {**proc, "timeout": 0.1})
                        time.sleep(0.12)
                        late = self.send("procedure_result", {**proc,"steps":["Observed result"],
                                         "trace":"fixture","outcome":"passed"})
                        assert late["outcome"] == "unavailable"
                        expired = self.send("check_run", p)
                        log = self.expand(json.loads((self.h.execution / expired["log"]).read_bytes()))
                        assert all(item["limitation"] == "check_deadline" for item in log["outputs"])
                self.send("procedure_begin", proc)
                self.send("procedure_result", {**proc,"steps":["Read tracked contract"],"trace":"fixture","outcome":"passed"})
        out = self.send("check_run", p)
        assert out["outcome"] == ("baseline_recorded" if stage == "baseline" else "passed"), out["outcome"]
        if repeat:
            again = self.send("check_run", p)
            assert not again["executed_check_ids"] and again["reused_evidence"]
        self.stop(ident)

    def begin(self, paths=None, additional=()):
        self.send("worktree_create", {"workspace": str(self.h.workspace / "task-worktrees")})
        self.send("checks_register", {"inventory":{"instructions":[],"ci":[]}, "additional":list(additional)})
        self.role("author", "executor")
        self.send("role_register", {"role_id":"reused", "kind":"reviewer", "lens_id":"code", "context_id":"author",
                  "fresh":True, "host":"codex", "launch_ref":"parity-fixture",
                  "capabilities":{"fresh_context":True}}, error="context_reused")
        self.send("start", {"role_id":"author","paths":paths or ["result.bin"]})
        self.run_checks("baseline")

    def freeze(self):
        self.stop("author")
        return self.send("candidate")

    def verify(self, repeat=False, check_gap=False):
        task = self.task
        stage = "integration" if task["worktree"]["integrated"] else "independent"
        self.run_checks(stage, repeat)
        verifier = stage + "-verification"
        packet = self.role(verifier, "reviewer", lens_id="verification")["packet"]
        self.send("review_start", {"role_id":verifier})
        verification = self.expand(json.loads(Path(packet).read_bytes()))["verification"]
        criteria = verification.pop("criteria")
        conclusion = {**verification, "role_id": verifier, "criteria_results":[
            {"criterion_id":c,"outcome":"passed","reason":"Fixture inspected","references":["result.bin"]}
            for c in criteria], "limitations":[], "trace":"fixture"}
        self.send("verification_result", {**conclusion,"criteria_results":[]}, error="verification_criteria")
        self.send("verification_result", conclusion)
        reviewer = stage + "-code"
        self.role(reviewer,"reviewer",lens_id="code")
        self.send("review_start", {"role_id":reviewer})
        if check_gap:
            with self.branch("gap"):
                failed = deepcopy(conclusion)
                for c in failed["criteria_results"]:
                    c.update(outcome="unavailable", check_request="Add the missing identity check")
                finding = self.send("verification_result", failed)["verification_result"]
                self.send("review_result", {"role_id":verifier,"verdict":"more_checks","findings":[],
                                            "test_integrity":"Inspect new check","trace":"fixture"})
                self.send("review_result", {"role_id":reviewer,"verdict":"pass","findings":[],"trace":"fixture"})
                before = self.task
                self.send("checks_extend", {"verification_result":finding["id"],"additional":[
                    {"id":"extra","source":"review","criteria":["AC-one"],"run":{"command":["git","status"]}}]})
                assert self.task["check_registry"]["revision"] == before["check_registry"]["revision"] + 1
                assert self.task["evidence"] == before["evidence"]
        self.send("review_result", {"role_id":verifier,"verdict":"pass","findings":[],
                                    "test_integrity":"Fixture inspected","trace":"fixture"})
        recommendation = {"severity":"recommendation","criteria":[],"path":"result.bin",
                          "problem":"Output lacks a format description","resolution":"Document the binary format"}
        self.send("review_result", {"role_id":reviewer,"verdict":"pass","findings":[recommendation],"trace":"fixture"})

    def revise(self, keep):
        # Replace the approved fixture plan through its public checkpoint, then check
        # that execution archives the previous run and preserves the accepted task.
        h = self.h
        old = self.state
        # A Git tree compares bytes. Both hosts must author exactly the same
        # revision even when their manifest encoders order mapping keys differently.
        plan = json.loads(json.dumps(old["tasks"]["TASK-one"]["plan"], sort_keys=True))
        tasks, records = [], [{"id":"REQ-one","sdd_record":"requirement","operation":"add"}]
        for n, suffix in enumerate(keep, 1):
            cid = "AC-" + suffix
            t = deepcopy(plan)
            t.update(id="TASK-"+suffix, number=n, covers=[cid], depends_on=[] if n == 1 else ["TASK-one"])
            t["verification"][0]["criteria"] = [cid]
            tasks.append(t)
            records.append({"sdd_record":"acceptance","id":cid,"requirement":"REQ-one",
                            "conditions":"Fixture","expected":"Result"})
        meta = {"schema_version":1,"change_id":"demo","language":"en"}
        document(h.change/"tasks.md",{**meta,"document_type":"tasks"},tasks)
        document(h.change/"specs/demo/spec.md",{**meta,"document_type":"spec","capability":"demo"},records)
        h.git("add","sdd/changes/demo/tasks.md","sdd/changes/demo/specs/demo/spec.md")
        h.git("commit","-m","Revise approved plan " + str(len(keep)))
        ref = h.git("for-each-ref","--format=%(refname)","refs/sdd/checkpoints/change/demo")
        h.git("update-ref",ref,h.git("rev-parse","HEAD"))
        r = self.send("revised_plan",{"instruction":{"text":"Execute this revision","source":"fixture"}},task_id=None)
        assert r["preserved_tasks"] == ["TASK-one"] and r["previous_run"] == old["run_id"]
        import uuid
        assert uuid.UUID(hex=r["run_id"]).version == 4 and r["run_id"] != old["run_id"]
        self.run_ids.append(r["run_id"])
        archived = self.expand(json.loads((h.execution / r["archive"]).read_bytes()))
        assert archived["tasks"]["TASK-one"] == old["tasks"]["TASK-one"]
        assert self.state["tasks"]["TASK-one"] == old["tasks"]["TASK-one"]
        assert list(sorted(self.state["tasks"])) == sorted(t["id"] for t in tasks)

    def lifecycle(self, on_transfer=None):
        from apply_transfers import BINARY, SOURCE, integrate_binary
        self.send("start", {"role_id":"missing","paths":["result.bin"]},error="dashboard_missing" if not (self.h.execution/"dashboard.html").exists() else "checks_missing")
        self.send("accept", error="commit_phase")
        self.begin(paths=["result.bin","check.py"],additional=[{"id":"planned","source":"fixture","criteria":["AC-one"],
                                "run":{"setup_required":"prepare the project check"}},
                               {"id":"inspection","source":"fixture","criteria":["AC-one"],
                                "execution_kind":"deterministic","run":{"procedure":"check.py"}}])
        self.send("check_setup", {"check_id":"planned","command":["git","rev-parse","HEAD"],"cwd":".",
                                  "description":"Inspect the frozen revision"})
        with self.branch("liveness"):
            live = {"host_trace":"Fixture inspected contexts","live_contexts":["author"]}
            assert self.send("resume",live,task_id=None)["status"] == "active"
            lost = self.send("resume",{**live,"live_contexts":[]},task_id=None)
            assert any(i["reason"] == "lost_role" for i in lost["issues"])
            self.role("replacement","executor",successor_of="author")
            resolved = {**live,"live_contexts":["replacement"],"resolutions":[
                {"reason":"lost_role","task_id":"TASK-one","role_id":"author","successor":"replacement","evidence":"fresh context"}]}
            self.send("resume",resolved,task_id=None)
            assert self.task["executor"] == "replacement"
        with self.branch("conflict"):
            conflict = self.send("spec_conflict", {"criteria":["AC-one"],"contract":"External result",
                                                   "reproduction":"Fixture reproduces conflict"})
            assert Path(conflict["material"]).is_file() and self.state["status"] == "blocked"
        self.send("budget_extend", {"budget":"review","limit":6,"source":"fixture","text":"Allow more reviews"})
        self.send("budget_extend", {"budget":"review","limit":6,"source":"fixture","text":"Same limit"}, error="finite_limit")
        (self.root / "result.bin").write_bytes(BINARY)
        (self.root / "check.py").write_bytes(SOURCE)
        self.freeze()
        with self.branch("repair"):
            repaired = self.send("repair", {"reason":"Reproduced defect","defect_evidence":"fixture"})
            assert repaired["status"] == "repairing"
        self.verify(repeat=True,check_gap=True)
        integrate_binary(self.h,self,self.root,on_transfer=on_transfer)
        self.send("candidate")
        # Successful transfer may reuse a complete suite and accepted review on the same Git tree.
        if self.task["status"] != "committing":
            self.verify()
        self.send("commit")
        self.send("accept")
        assert self.h.process(self.implementation,"available",{"directory":str(self.h.execution)})["result"] == ["TASK-two"]
        tree = Path(self.task["worktree"]["path"])
        unknown = tree / "unrelated.txt"
        unknown.write_bytes(b"owned by somebody else")
        self.send("worktree_remove", error="unknown_worktree_data")
        assert unknown.read_bytes() == b"owned by somebody else"
        unknown.unlink()
        self.send("worktree_remove")
        final = self.finalize()
        assert final["result"] == "partial" and final["accepted_criteria"] == ["AC-one"]
        self.revise(["one","two","three"])
        self.revise(["one"])
        final = self.finalize()
        assert final["result"] == "complete" and final["missing"] == []

    def finalize(self):
        result = self.send("finalize", task_id=None)
        assert result["decisions"] and result["decisions"][0]["action"] == "defer"
        assert result["decisions"][0]["finding_id"] == result["recommendations"][0]["finding_id"]
        files = {name: (self.h.execution / name).read_bytes().decode("utf-8")
                 for name in ("summary.md", "technical-debt.md")}
        snapshot = "Snapshot: " + self.state["updated_at"]
        assert snapshot in files["summary.md"]
        files["summary.md"] = files["summary.md"].replace(snapshot, "Snapshot: <timestamp>", 1)
        self.trace.append(["final documents", files])
        return result


def compare_lifecycle(h, seed=None, *, refresh=False):
    from apply_transfers import capture_reviewed_seed, git_transition_cases
    os.environ.update(GIT_AUTHOR_DATE="2025-01-01T00:00:00Z", GIT_COMMITTER_DATE="2025-01-01T00:00:00Z")
    if seed is None:
        h.fixture()
        h.initialized()
        seed = h.workspace / "seed"
        shutil.copytree(h.project, seed)
    else:
        h.project.rename(h.workspace / "completed-operations")
        shutil.copytree(seed, h.project)
    reviewed = None
    traces = []
    for implementation in h.commands:
        started = time.monotonic()
        if implementation == "Go":
            h.project.rename(h.workspace / "completed-oracle")
            worktrees = h.workspace / "task-worktrees"
            if worktrees.exists():
                worktrees.rename(h.workspace / "oracle-worktrees")
            shutil.copytree(seed, h.project)
        driver = Driver(h, implementation)
        def capture():
            nonlocal reviewed
            if refresh and implementation == "Python":
                reviewed = capture_reviewed_seed(h, driver)
        driver.lifecycle(on_transfer=capture)
        trace = json.dumps(driver.trace,sort_keys=True)
        for n, run_id in enumerate(driver.run_ids):
            trace = trace.replace(run_id, f"<revised-run-{n}>")
        traces.append(json.loads(trace))
        (h.workspace / f"{implementation}-events.json").write_text(trace, encoding="utf-8")
        print(f"{implementation} event lifecycle {time.monotonic() - started:.2f} s", flush=True)
    pilot.equal(*traces, "/events", ("Python","Go"))
    print("Execution lifecycle PASS", flush=True)
    if refresh:
        git_transition_cases(h, reviewed, include_binary=False)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basetemp", type=Path, required=True)
    args = parser.parse_args()
    base = args.basetemp.resolve()
    if not base.is_dir() or any((p / ".git").exists() for p in (base, *base.parents)):
        parser.error("Use an existing temporary directory outside Git worktrees")
    work = Path(tempfile.mkdtemp(prefix="sdd-events-", dir=base))
    print(work, flush=True)
    try:
        h = ApplyHarness(work, Path(__file__).resolve().parents[2], Path(sys.executable), started + 118)
        compare_lifecycle(h)
    finally:
        print(f"Event suite elapsed {time.monotonic()-started:.2f} s", flush=True)


if __name__ == "__main__":
    main()
