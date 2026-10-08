"""Exact command registry and independently produced, snapshot-bound evidence."""
import json
from pathlib import Path
import subprocess
import time
import os
import signal
from .common import contained, digest, git, now, require, write_json
from .state import snapshot


def root_for(state, task):
    return task["worktree"]["path"] if task.get("worktree") and not task["worktree"].get("integrated") else state["basis"]["project_root"]


def candidate(state, task):
    return {"source": snapshot(state, root_for(state, task)), "manifest": digest(state["basis"]["manifest"]), "checks": digest(task["checks"]), "root": root_for(state, task)}


def current(state, task):
    require(task["candidate"] and task["candidate"] == candidate(state, task), "stale_candidate", "Files, verification registry or normative inputs changed")


def independent(state, task, role_id, kinds):
    role = state["roles"].get(role_id)
    require(role and role["kind"] in kinds and role["task_id"] == task["plan"]["id"] and role["status"] == "active", "role_unavailable", "Active independent role required")
    authors = [state["roles"][r]["context_id"] for r in task["roles"] if state["roles"][r]["kind"] == "executor"]
    require(role["context_id"] not in authors and role["fresh"] is True, "role_not_independent", "Author context cannot independently verify or review")
    return role


def valid_evidence(state, task, directory, stage=None):
    if stage != "final":
        current(state, task)
    expected = candidate(state, task) if stage == "final" else task["candidate"]
    matches, seen = [], set()
    for item in reversed(task["evidence"]):
        if item["candidate"] != expected or item["stage"] not in ({stage} if stage else {"independent", "integration"}):
            continue
        if item["check_id"] in seen:
            continue
        seen.add(item["check_id"])
        require(item["outcome"] == "passed", "required_checks", "Latest required check is failed, unavailable or stale")
        path = contained(directory, item["log"])
        require(path.is_file() and digest(path.read_bytes()) == item["log_hash"], "evidence_corrupt", item["log"])
        log_data = json.loads(path.read_text(encoding="utf-8"))
        for output in log_data.get("outputs", []):
            if output.get("procedure_log"):
                linked = contained(directory, output["procedure_log"])
                require(linked.is_file() and digest(linked.read_bytes()) == output["procedure_log_hash"], "evidence_corrupt", "Procedure log changed")
        require(item["role_id"] in state["roles"], "unknown_role", "Evidence role missing")
        role = state["roles"][item["role_id"]]
        require(stage != "final" or role["kind"] == "final_verifier", "final_role", "A fresh final verifier is required")
        authors = {r["context_id"] for r in state["roles"].values() if r["kind"] == "executor" and (stage == "final" or r["task_id"] == task["plan"]["id"])}
        require(role["context_id"] not in authors and role["fresh"], "role_not_independent", "Evidence author is not independent")
        matches.append(item)
    required = {c["id"] for c in task["checks"]}
    require(required and required <= {m["check_id"] for m in matches}, "required_checks", "Every required command/procedure must pass at this candidate")
    return matches


def run_command(command, cwd, timeout):
    started, stamp = time.monotonic(), now()
    try:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=10)
            return {"command": command, "cwd": str(cwd), "started_at": stamp, "duration_seconds": time.monotonic() - started, "exit_code": None, "stdout": stdout.decode("utf-8", "replace"), "stderr": stderr.decode("utf-8", "replace"), "outcome": "unavailable", "limitation": "timeout"}
        code = process.returncode
        outcome = "passed" if code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code, outcome = exc.stdout or b"", exc.stderr or b"", None, "unavailable"
    except OSError as exc:
        stdout, stderr, code, outcome = b"", str(exc).encode(), None, "unavailable"
    return {"command": command, "cwd": str(cwd), "started_at": stamp, "duration_seconds": time.monotonic() - started, "exit_code": code, "stdout": stdout.decode("utf-8", "replace"), "stderr": stderr.decode("utf-8", "replace"), "outcome": outcome}


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task required")
    kind, p = event["type"], event["payload"]
    if kind == "checks_register":
        require(task["status"] == "pending" and not task["checks"], "registry_frozen", "Register once before execution")
        checks = []
        for i, planned in enumerate(task["plan"]["verification"]):
            checks.append({"id": f"plan-{i + 1}", "criteria": planned["criteria"], "source": "tasks.md", "location": planned["location"], "run": planned["run"], "cwd": ".", "configuration": {}, "setup": None})
        require(p.get("inventory") and set(p["inventory"]) == {"instructions", "ci"}, "inventory_required", "Record inspected project instruction and CI files, including an explicit empty inventory")
        for check in p.get("additional", []):
            require(check.get("id") and check.get("source") and check.get("run"), "check_schema", "Additional required checks need ID, source and exact run")
            checks.append({**check, "setup": None, "cwd": check.get("cwd", "."), "configuration": check.get("configuration", {})})
        require(len({c["id"] for c in checks}) == len(checks), "duplicate_check", "Duplicate check ID")
        task["checks"], task["inventory"] = checks, p["inventory"]
        return {"checks": checks}
    if kind == "checks_extend":
        require(task["status"] == "verifying" and task["reviews"] and task["reviews"][-1]["verdict"] == "more_checks", "extension_phase", "A reviewer must request additional checks")
        current(state, task)
        additions = p.get("additional", [])
        require(additions and p.get("review_round") == task["reviews"][-1]["round_id"], "extension_evidence", "Reference the review requesting additional checks")
        for check in additions:
            require(check.get("id") and check.get("source") and check.get("run", {}).get("command") and check.get("criteria") and set(check["criteria"]) <= set(task["plan"]["covers"]), "check_schema", "Add exact runnable checks with scoped AC")
            require(check["id"] not in {c["id"] for c in task["checks"]}, "duplicate_check", "Existing checks cannot be replaced")
            task["checks"].append({**check, "setup": None, "cwd": check.get("cwd", "."), "configuration": check.get("configuration", {})})
        task["candidate"] = candidate(state, task)
        return {"checks": task["checks"], "candidate": task["candidate"]}
    if kind == "check_setup":
        check = next((c for c in task["checks"] if c["id"] == p.get("check_id")), None)
        require(check and ("setup_required" in check["run"] or "procedure" in check["run"]) and check["setup"] is None, "setup_not_planned", "Only planned, unresolved setup or procedure may be registered")
        require(task["status"] in {"running", "repairing"}, "setup_phase", "Prepare checks within their task")
        require(p.get("command") and p.get("description") and task.get("baseline_checks"), "setup_evidence", "Need baseline check inventory and preparation description")
        check["setup"] = {"command": p["command"], "cwd": p.get("cwd", "."), "configuration": p.get("configuration", {}), "description": p["description"], "before": task["start_snapshot"], "after": snapshot(state, root_for(state, task))}
        return {"setup": check}
    if kind == "candidate":
        require(task["status"] in {"running", "repairing", "integrating"}, "candidate_phase", "Candidate requires completed implementation or integration")
        require(task.get("executor") and state["roles"][task["executor"]]["status"] == "finished", "writer_active", "Executor must finish writing before freezing")
        require(not any(state["roles"][r]["kind"] == "executor" and state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "All task writers must stop before freezing")
        require(all("setup_required" not in c["run"] or c["setup"] for c in task["checks"]), "setup_pending", "Resolve all planned setup")
        frozen = candidate(state, task)
        baseline = task.get("freeze_base", task["start_snapshot"])["files"]
        current_files = frozen["source"]["files"]
        changed = {p for p in set(baseline) | set(current_files) if baseline.get(p) != current_files.get(p)}
        require(changed <= set(task["paths"]), "candidate_scope", "Changes outside task ownership: " + ", ".join(sorted(changed - set(task["paths"]))))
        task["candidate"] = frozen
        task["status"] = "verifying"
        return {"candidate": task["candidate"]}
    if kind == "procedure_begin":
        stage = p.get("stage")
        require(stage in {"baseline", "self", "independent", "integration", "final"}, "procedure_stage", "Unknown stage")
        check = next((c for c in task["checks"] if c["id"] == p.get("check_id")), None)
        require(check and "procedure" in check["run"] and not check["setup"], "procedure_check", "Use the registered procedure without replacing it")
        if stage != "self":
            independent(state, task, p.get("role_id"), {"verifier", "reviewer", "final_verifier"})
        else:
            require(p.get("role_id") == task.get("executor"), "executor_required", "Assigned executor required")
        if stage not in {"baseline", "self", "final"}:
            current(state, task)
        if stage == "final":
            require(task["status"] == "accepted" and state["roles"][p["role_id"]]["kind"] == "final_verifier", "final_role", "Fresh final verifier required")
        root = root_for(state, task)
        path = contained(root, check["run"]["procedure"])
        require(path.is_file(), "procedure_unavailable", str(path))
        pending = task.setdefault("procedures", {})
        require(check["id"] not in pending, "procedure_active", "Finish the existing procedure attempt")
        pending[check["id"]] = {"role_id": p["role_id"], "stage": stage, "candidate": candidate(state, task) if stage == "final" else task["candidate"], "before": snapshot(state, root), "path": str(path), "sha256": digest(path.read_bytes()), "started_at": now()}
        return pending[check["id"]]
    if kind == "procedure_result":
        pending = task.get("procedures", {}).get(p.get("check_id"))
        require(pending and p.get("role_id") == pending["role_id"], "procedure_owner", "Match the registered procedure attempt")
        require(p.get("outcome") in {"passed", "failed", "unavailable", "skipped", "unstable"} and p.get("steps") and p.get("trace"), "procedure_evidence", "Actual steps, outcome and host trace required")
        after = snapshot(state, root_for(state, task))
        outcome = p["outcome"] if after == pending["before"] else "stale"
        relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/{event['event_id']}.json"
        record = {"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], **pending, "after": after, "steps": p["steps"], "trace": p["trace"], "outcome": outcome}
        path = contained(directory, relative)
        write_json(path, record)
        item = {"check_id": p["check_id"], "stage": pending["stage"], "role_id": p["role_id"], "candidate": pending["candidate"], "outcome": outcome, "log": relative, "log_hash": digest(path.read_bytes()), "time": now(), "head": git(root_for(state, task), "rev-parse", "HEAD"), "procedure": True}
        task["evidence"].append(item)
        del task["procedures"][p["check_id"]]
        return item
    require(kind == "check_run", "check_operation", kind)
    stage = p.get("stage")
    require(stage in {"baseline", "self", "independent", "integration", "final"}, "check_stage", "Unknown verification stage")
    role_id = p.get("role_id")
    if stage in {"independent", "integration", "final"}:
        independent(state, task, role_id, {"verifier", "reviewer", "final_verifier"})
        require(task["status"] in {"verifying", "reviewing", "accepted", "integrating"}, "check_phase", "No frozen candidate")
        if stage != "final":
            current(state, task)
        else:
            require(state["roles"][role_id]["kind"] == "final_verifier" and task["status"] == "accepted", "final_role", "Final verifier checks accepted tasks at final HEAD")
        if task.get("last_check_failed"):
            require(task["active_repair"], "repair_cycle_required", "A retry after failure must reserve a repair cycle")
    elif stage == "baseline" and role_id != task.get("executor"):
        independent(state, task, role_id, {"verifier"})
    else:
        require(role_id == task.get("executor"), "executor_required", "Self-check belongs to executor")
    require(task["checks"], "checks_missing", "Register verification first")
    root = Path(root_for(state, task))
    before = snapshot(state, root)
    if stage == "baseline":
        require(not task.get("baseline_checks") and before == task["start_snapshot"], "baseline_changed", "Capture the initial checks before any implementation edits")
    outputs = []
    for check in task["checks"]:
        run = check["setup"] or check["run"]
        if check["setup"] and check.get("location") and not contained(root, check["location"]).exists():
            outputs.append({"check_id": check["id"], "outcome": "unavailable", "description": "Previously prepared required check location is missing"})
            continue
        if "command" not in run:
            if stage == "baseline" and "setup_required" in run:
                outputs.append({"check_id": check["id"], "outcome": "planned_absence", "description": run["setup_required"]})
                continue
            if "procedure" in run:
                tested = candidate(state, task) if stage == "final" else task["candidate"]
                latest = next((e for e in reversed(task["evidence"]) if e["check_id"] == check["id"] and e["stage"] == stage and e["candidate"] == tested and e.get("procedure")), None)
                if latest:
                    path = contained(directory, latest["log"])
                    require(path.is_file() and digest(path.read_bytes()) == latest["log_hash"], "evidence_corrupt", "Procedure evidence changed")
                    outputs.append({"check_id": check["id"], "outcome": latest["outcome"], "procedure_log": latest["log"], "procedure_log_hash": latest["log_hash"]})
                    continue
            outputs.append({"check_id": check["id"], "outcome": "unavailable", "description": "No executable command for required procedure"})
            continue
        relative = run.get("cwd", check["cwd"])
        cwd = root if relative == "." else contained(root, relative)
        result = run_command(run["command"], cwd, p.get("timeout", 300))
        result.update(check_id=check["id"], configuration=run.get("configuration", check["configuration"]), criteria=check["criteria"])
        outputs.append(result)
    after = snapshot(state, root)
    tested_candidate = candidate(state, task) if stage == "final" else task["candidate"]
    record = {"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], "task_id": task["plan"]["id"], "role_id": role_id, "stage": stage, "candidate": tested_candidate, "before": before, "after": after, "outputs": outputs}
    relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/{event['event_id']}.json"
    path = contained(directory, relative)
    write_json(path, record)
    outcome = "passed" if all(r["outcome"] == "passed" for r in outputs) and before == after else "failed"
    if any(r["outcome"] == "unavailable" for r in outputs):
        outcome = "unavailable"
    if stage == "baseline":
        task["baseline_checks"] = record
        if all(r["outcome"] in {"passed", "planned_absence"} for r in outputs) and before == after:
            return {"outcome": "baseline_recorded", "log": relative}
        state["status"] = "blocked"
        state["blockers"].append({"reason": "baseline_failed", "task_id": task["plan"]["id"], "resume_condition": "Resolve or explicitly scope the pre-existing failure", "log": relative})
    for result in outputs:
        task["evidence"].append({"check_id": result["check_id"], "stage": stage, "role_id": role_id, "candidate": tested_candidate, "outcome": result["outcome"] if before == after else "stale", "log": relative, "log_hash": digest(path.read_bytes()), "time": now(), "head": git(root, "rev-parse", "HEAD")})
    if stage != "self" or outcome != "passed":
        task["last_check_failed"] = outcome != "passed"
        if task["active_repair"] and outcome != "unavailable" and stage in {"independent", "integration", "final"}:
            task["repair_cycles"].append({"id": task["active_repair"], "outcome": outcome, "log": relative})
            task["active_repair"] = None
        if outcome != "passed":
            from .budgets import failure
            failure(state, task, "test", outcome)
    return {"outcome": outcome, "log": relative}
