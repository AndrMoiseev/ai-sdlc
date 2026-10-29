"""Whole-result checks at one integrated source, without a synthetic task owner."""
from copy import deepcopy
import json
from pathlib import Path

from . import artifact_storage as artifacts
from . import check_evidence
from .common import contained, digest, now, require, write_json
from .check_registry import confirmed_tasks, confirmed_revision, selected, refactoring, strings
from .state import snapshot, clean_source
from .inputs import read_plan_document, document_paths


def criteria(state):
    if not refactoring(state):
        allowed = {ident for task in state["tasks"].values() for ident in task["plan"]["covers"]}
        records = [record for entry in document_paths(state["basis"])
                   if entry.startswith("specs/") and entry.endswith("/spec.md")
                   for record in read_plan_document(state["basis"], entry)
                   if record["sdd_record"] == "acceptance" and record["id"] in allowed]
        require({record["id"] for record in records} == allowed, "criteria_uncovered", "Every covers criterion needs its approved specification")
        return {record["id"]: record for record in records}
    return {record["id"]: record for record in read_plan_document(state["basis"], "design.md") if record["sdd_record"] == "criterion"}


def registry(state):
    result = state.get("final_checks")
    require(result and result["history"] and result["revision"] == len(result["history"])
            and result["history"][-1]["checks"] == result["checks"],
            "final_registry_missing", "Register whole-result checks without a task owner")
    return result


def applicable(state):
    whole = registry(state)["checks"]
    if not refactoring(state):
        return whole
    local = selected(state, None, final=True)
    require(not {check["id"] for check in whole} & {check["id"] for check in local},
            "duplicate_check", "Whole and task checks have distinct identities")
    return local + whole


def retired(state):
    if not refactoring(state):
        return []
    result = {}
    for task in confirmed_tasks(state):
        for entry in task["check_registry"]["history"][:confirmed_revision(task)]:
            transition = entry.get("transition")
            if not transition:
                continue
            after = {check["id"] for check in transition["after"]}
            for check in transition["before"]:
                if check["id"] not in after:
                    result[check["id"]] = {"check_id": check["id"], "criteria": check["criteria"],
                        "task_id": task["plan"]["id"], "reason": transition["reason"],
                        "basis": transition["basis"], "event_id": entry["event_id"]}
    active = {check["id"] for check in selected(state, None, final=True)}
    return [record for ident, record in result.items() if ident not in active]


def basis(state):
    source = snapshot(state)
    clean_source(source)
    result = {"work_kind": state["basis"].get("work_kind", "change"), "change_id": state["change_id"], "run_id": state["run_id"],
            "source": source, "manifest": digest({"head": state["basis"]["head"], "document_paths": document_paths(state["basis"])}),
            "registry_revision": registry(state)["revision"], "checks": applicable(state)}
    if refactoring(state):
        result["task_revisions"] = {key: confirmed_revision(task) for key, task in state["tasks"].items()}
    else:
        result["task_checks"] = {key: deepcopy(task["checks"]) for key, task in state["tasks"].items()}
    return result


def independent(state, role_id, active=True):
    role = state["roles"].get(role_id)
    require(role and role["kind"] == "final_verifier" and role["task_id"] is None
            and role["status"] in ({"active"} if active else {"active", "finished"}),
            "final_role", "Use a run-level fresh final verifier; lost-role proof requires fresh execution")
    authors = {role["context_id"] for role in state["roles"].values() if role["kind"] == "executor"}
    require(role["fresh"] and role["context_id"] not in authors, "role_not_independent", "Final evidence is independent of every author")
    return role


def record_revision(result, event):
    result["revision"] += 1
    result["history"].append({"revision": result["revision"], "event_id": event["event_id"],
                              "checks": deepcopy(result["checks"])})


def register(state, event):
    from .verification import require_command
    require(not state.get("final_checks"), "registry_frozen", "Register whole checks once")
    payload = event["payload"]
    require(payload.get("inventory") and set(payload["inventory"]) == {"instructions", "ci"},
            "inventory_required", "Record inspected instructions and CI")
    if not refactoring(state):
        ready(state)
    checks = [{"id": item["id"], "criteria": item["criteria"], "source": "tasks.md",
               "location": item["location"], "run": item["run"], "setup_task": item.get("setup_task"),
               "setup": None, "cwd": ".", "configuration": {}} for item in state.get("verification", {}).values()]
    allowed = set(criteria(state)) | {key for key, item in state.get("acceptance", {}).items() if item["lifetime"] == "persistent"}
    require(isinstance(payload.get("additional", []), list), "check_schema", "Additional checks must be a list")
    for item in payload.get("additional", []):
        require(isinstance(item, dict), "check_schema", "Additional checks must be objects")
        require(item.get("id") and item.get("source") and item.get("run") and strings(item.get("criteria")) and item["criteria"]
                and set(item["criteria"]) <= allowed, "check_schema", "Bind additional mandatory checks to approved final criteria")
        require(isinstance(item["id"], str) and isinstance(item["source"], str)
                and strings(item["criteria"]) and isinstance(item["run"], dict)
                and set(item["run"]) in ({"command"}, {"procedure"})
                and isinstance(item.get("cwd", "."), str) and isinstance(item.get("configuration", {}), dict),
                "check_schema", "Additional final checks need an exact command or procedure and scoped criteria")
        if "procedure" in item["run"]:
            require(isinstance(item["run"]["procedure"], str) and item["run"]["procedure"].strip(),
                    "check_schema", "Procedure path required")
            contained(state["basis"]["project_root"], item["run"]["procedure"])
        if item.get("cwd", ".") != ".":
            contained(state["basis"]["project_root"], item["cwd"])
        checks.append({**item, "setup": None, "cwd": item.get("cwd", "."), "configuration": item.get("configuration", {})})
    require(checks and len({item["id"] for item in checks}) == len(checks), "duplicate_check", "Distinct whole-result checks required")
    for check in checks:
        if "command" in check["run"]:
            require_command(check["run"]["command"])
    result = {"checks": checks, "revision": 0, "history": [], "evidence": [], "procedures": {},
              "failures": {}, "inventory": payload["inventory"]}
    record_revision(result, event)
    state["final_checks"] = result
    state["final"] = None
    applicable(state)
    return {"checks": checks, "registry_revision": result["revision"]}


def setup(state, event):
    from .verification import require_command, root_for
    result, payload = registry(state), event["payload"]
    check = next((check for check in result["checks"] if check["id"] == payload.get("check_id")), None)
    require(check and check.get("setup_task") and check["setup"] is None
            and "setup_required" in check["run"], "setup_not_planned", "Whole setup needs its approved setup_task")
    task = state["tasks"][check["setup_task"]]
    require(task["status"] in {"running", "repairing"} and task.get("baseline_checks"),
            "setup_phase", "Prepare within the assigned task after baseline")
    require(state["roles"].get(task.get("executor"), {}).get("status") == "active" and payload.get("description"),
            "setup_evidence", "Assigned task executor and preparation description required")
    require_command(payload.get("command"))
    check["setup"] = {"command": payload["command"], "cwd": payload.get("cwd", "."),
        "configuration": payload.get("configuration", {}), "description": payload["description"],
        "before": task["start_snapshot"], "after": snapshot(state, root_for(state, task))}
    record_revision(result, event)
    state["final"] = None
    return {"setup": check}


def ready(state):
    from .commits import confirm
    require(all(task["status"] == "accepted" and task["commits"]
                and (bool((task.get("worktree") or {}).get("integrated")) if refactoring(state) else
                     not task.get("worktree") or task["worktree"].get("integrated"))
                for task in state["tasks"].values()), "final_tasks", "Accept and integrate every task before final checks")
    for task in state["tasks"].values():
        for commit in task["commits"]:
            confirm(state, task, commit)
        if refactoring(state):
            require(confirmed_revision(task) == task["check_registry"]["revision"],
                    "registry_unconfirmed", "Confirm every applicable registry transition")


def procedure(state, event, directory):
    payload, result = event["payload"], registry(state)
    independent(state, payload.get("role_id"))
    ready(state)
    current = basis(state)
    check = next((check for check in current["checks"] if check["id"] == payload.get("check_id")), None)
    require(check and "procedure" in check["run"] and not check["setup"], "procedure_check", "Use the exact applicable procedure")
    if event["type"] == "procedure_begin":
        require(not result["failures"], "repair_owner_required", "Reserve an owned repair before a failed final procedure retry")
        require(payload.get("stage") == "final" and check["id"] not in result["procedures"],
                "procedure_stage", "Begin a new final procedure")
        path = contained(state["basis"]["project_root"], check["run"]["procedure"])
        require(path.is_file(), "procedure_unavailable", str(path))
        result["procedures"][check["id"]] = {"basis": current, "role_id": payload["role_id"],
                                              "started_at": now(), "attempt_id": event["event_id"]}
        state["final"] = None
        return {"procedure": str(path), "basis": current, "attempt_id": event["event_id"]}
    pending = result["procedures"].get(check["id"])
    require(pending and pending["role_id"] == payload["role_id"], "procedure_owner", "Match the registered attempt")
    require(payload.get("outcome") in {"passed", "failed", "unavailable", "skipped", "unstable"}
            and payload.get("steps") and payload.get("trace"), "procedure_evidence", "Actual steps, trace and outcome required")
    outcome = payload["outcome"] if pending["basis"] == current else "stale"
    relative = f"runs/{state['run_id']}/final/{event['event_id']}.json"
    path = artifacts.contained(directory, relative)
    write_json(path, {**payload, **pending, "outcome": outcome})
    item = {"check_id": check["id"], "criteria": check["criteria"], "basis": pending["basis"], "role_id": payload["role_id"],
            "outcome": outcome, "attempt_id": pending.get("attempt_id"),
            "log": relative, "log_hash": digest(artifacts.read_bytes(path)), "procedure": True}
    result["evidence"].append(item)
    if outcome != "passed":
        result["failures"][check["id"]] = item
    del result["procedures"][check["id"]]
    state["final"] = None
    return item


def procedure_evidence(state, check, directory, current):
    """The latest attempt supersedes earlier proof even when its basis is unchanged."""
    result = registry(state)
    if check["id"] in result["procedures"]:
        return {"outcome": "unavailable", "description": "procedure_pending"}
    item = next((item for item in reversed(result["evidence"])
                 if item.get("procedure") and item["check_id"] == check["id"]), None)
    if not item:
        return {"outcome": "unavailable", "description": "procedure_missing"}
    if state["roles"].get(item["role_id"], {}).get("status") == "lost":
        return {"outcome": "unavailable", "description": "final_role_lost"}
    independent(state, item["role_id"], active=False)
    path = artifacts.contained(directory, item["log"])
    require(artifacts.is_file(path) and digest(artifacts.read_bytes(path)) == item["log_hash"],
            "evidence_corrupt", item["log"])
    record = json.loads(artifacts.read_bytes(path))
    require(record.get("basis") == item["basis"] and record.get("role_id") == item["role_id"]
            and record.get("check_id") == check["id"] and record.get("outcome") == item["outcome"]
            and record.get("attempt_id") == item.get("attempt_id"),
            "evidence_basis", "Procedure proof must name its exact attempt, role and outcome")
    outcome = item["outcome"] if item["basis"] == current else "stale"
    return {"outcome": outcome, "procedure_log": item["log"], "procedure_log_hash": item["log_hash"],
            "procedure_attempt": item.get("attempt_id")}


def reconcile_procedures(state, predecessor, successor, resolution, event, directory):
    """Archive explicitly abandoned work; the successor must execute a fresh attempt."""
    result = registry(state)
    pending = {ident: value for ident, value in result["procedures"].items() if value["role_id"] == predecessor["role_id"]}
    supplied = resolution.get("abandon_procedures", [])
    require(isinstance(supplied, list) and len(supplied) == len(set(supplied)) and set(supplied) == set(pending),
            "procedure_reconciliation", "Explicitly list every unfinished predecessor check in abandon_procedures")
    for ident, attempt in pending.items():
        relative = f"runs/{state['run_id']}/final/{event['event_id']}-{digest(ident)[:16]}.json"
        path = artifacts.contained(directory, relative)
        record = {**attempt, "check_id": ident, "outcome": "abandoned", "successor": successor["role_id"],
                  "resolution": resolution, "trace": event["payload"]["host_trace"]}
        write_json(path, record)
        result["evidence"].append({"check_id": ident, "basis": attempt["basis"], "role_id": attempt["role_id"],
            "attempt_id": attempt.get("attempt_id"), "outcome": "abandoned", "procedure": True,
            "log": relative, "log_hash": digest(artifacts.read_bytes(path))})
        del result["procedures"][ident]
    if pending:
        state["final"] = None


def execute(state, check, directory, current, timeout):
    from . import verification
    from .inputs import spec_modules
    root = Path(state["basis"]["project_root"])
    run = check["setup"] or check["run"]
    if check.get("location"):
        location = spec_modules("paths").verification_location(root, check["location"])
        if not location.exists():
            return {"outcome": "unavailable", "description": "Required verification location is missing"}
    if "command" in run:
        cwd = run.get("cwd", check["cwd"])
        output = verification.check_runner.run_command(run["command"], root if cwd == "." else contained(root, cwd), timeout)
        output["configuration"] = run.get("configuration", check["configuration"])
        output["_report_capture"] = check_evidence.capture_reports(output)
        return output
    if "procedure" in run:
        return procedure_evidence(state, check, directory, current)
    return {"outcome": "unavailable", "description": "Required whole-result setup or procedure is unavailable"}


def run(state, event, directory):
    payload, result = event["payload"], registry(state)
    require(payload.get("stage") == "final", "check_stage", "Run-level checks require final stage")
    independent(state, payload.get("role_id"))
    ready(state)
    require(not result["failures"], "repair_owner_required", "Assign failed final checks to an authorized repair task before retry")
    before = basis(state)
    outputs = []
    for check in before["checks"]:
        output = execute(state, check, directory, before, payload.get("timeout", 300))
        outputs.append({**output, "check_id": check["id"], "criteria": check["criteria"]})
    after = snapshot(state)
    unchanged = before["source"] == after
    relative = f"runs/{state['run_id']}/final/{event['event_id']}.json"
    path = artifacts.contained(directory, relative)
    record = {"basis": before, "role_id": payload["role_id"], "task_id": None, "stage": "final", "after": after, "outputs": outputs}
    summary = check_evidence.persist(state, record, before["checks"], directory, event["event_id"])
    write_json(path, record)
    outcome = "passed" if unchanged and all(output["outcome"] == "passed" for output in outputs) else "failed"
    if not summary["evidence_complete"]:
        outcome = "failed"
    for output in outputs:
        item = {"check_id": output["check_id"], "criteria": output["criteria"], "basis": before,
                "role_id": payload["role_id"], "outcome": (output["outcome"] if output["evidence_complete"] else "unavailable") if unchanged else "stale",
                "log": relative, "log_hash": digest(artifacts.read_bytes(path)), "time": now()}
        result["evidence"].append(item)
        if item["outcome"] != "passed":
            result["failures"][item["check_id"]] = item
    state["final"] = None
    return {"outcome": outcome, "log": relative, "failures": list(result["failures"]), "summary": summary}


def evidence(state, directory):
    current, matches, gaps = basis(state), [], []
    validated = set()
    for check in current["checks"]:
        latest_procedure = None
        if "procedure" in (check["setup"] or check["run"]):
            latest_procedure = procedure_evidence(state, check, directory, current)
            if latest_procedure["outcome"] != "passed":
                gaps.append({"check_id": check["id"], "criteria": check["criteria"], "location": check.get("location"),
                             "reason": latest_procedure.get("description", latest_procedure["outcome"])})
                continue
        item = next((item for item in reversed(registry(state)["evidence"]) if not item.get("procedure")
                     and item["check_id"] == check["id"]), None)
        if not item or item["basis"] != current or item["outcome"] != "passed":
            gaps.append({"check_id": check["id"], "criteria": check["criteria"], "location": check.get("location"),
                         "reason": item["outcome"] if item and item["basis"] == current else "final_evidence_missing"})
            continue
        if state["roles"].get(item["role_id"], {}).get("status") == "lost":
            gaps.append({"check_id": check["id"], "criteria": check["criteria"], "location": check.get("location"),
                         "reason": "final_role_lost"})
            continue
        independent(state, item["role_id"], active=False)
        path = artifacts.contained(directory, item["log"])
        require(artifacts.is_file(path) and digest(artifacts.read_bytes(path)) == item["log_hash"], "evidence_corrupt", item["log"])
        record = json.loads(artifacts.read_bytes(path))
        require(record["basis"] == current and record["role_id"] == item["role_id"] and record["task_id"] is None
                and record["stage"] == "final" and record["after"] == current["source"], "evidence_basis", "Final log must match the exact integrated state")
        output = next((value for value in record["outputs"] if value["check_id"] == check["id"]), None)
        require(output and output["outcome"] == "passed" and output["criteria"] == check["criteria"], "evidence_basis", "Registered final check missing from log")
        command = (check["setup"] or check["run"]).get("command")
        if command:
            require(output.get("command") == command and output.get("exit_code") == 0, "evidence_command", "Exact registered command must pass")
            if not refactoring(state):
                run = check["setup"] or check["run"]
                cwd = run.get("cwd", check["cwd"])
                root = Path(state["basis"]["project_root"])
                require(output.get("cwd") == str(root if cwd == "." else contained(root, cwd))
                        and output.get("configuration") == run.get("configuration", check["configuration"]),
                        "evidence_command", "Registered command cwd and configuration must match")
        else:
            if any(output.get(key) != latest_procedure.get(key)
                   for key in ("procedure_log", "procedure_log_hash", "procedure_attempt")):
                gaps.append({"check_id": check["id"], "criteria": check["criteria"], "location": check.get("location"),
                             "reason": "procedure_superseded"})
                continue
            linked = artifacts.contained(directory, output["procedure_log"])
            require(artifacts.is_file(linked) and digest(artifacts.read_bytes(linked)) == output["procedure_log_hash"], "evidence_corrupt", "Procedure log changed")
        if item["log_hash"] not in validated:
            check_evidence.validate(state, record, current["checks"], directory)
            validated.add(item["log_hash"])
        matches.append(item)
    return current, matches, gaps


def repair(state, task, payload, directory, event):
    """Establish ownership before reopening an author; keep existing task budgets."""
    result = registry(state)
    failed = payload.get("final_checks", [])
    require(failed and set(failed) <= result["failures"].keys() and payload.get("defect_evidence"),
            "repair_evidence", "Name failed final checks and reproducible ownership evidence")
    paths = payload.get("paths", [])
    if not task or not paths or not set(paths) <= set(task["paths"]):
        from .resume import transition
        return transition(state, task, {**event, "type": "spec_conflict", "payload": {
            "reproduction": payload["defect_evidence"], "criteria": sorted({criterion for ident in failed for criterion in result["failures"][ident]["criteria"]}),
            "contract": "Final defect has no established authorized repair owner; revise the plan or establish ownership"}}, directory)
    from .budgets import repair as reserve
    response = reserve(state, task, {**payload, "test_failure": True})
    if response.get("status") == "repairing":
        result.setdefault("repairs", []).append({"task_id": task["plan"]["id"], "checks": failed,
            "paths": paths, "evidence": payload["defect_evidence"], "cycle": response["cycle"]})
        for ident in failed:
            del result["failures"][ident]
        state["final"] = None
    return response


def transition(state, event, directory):
    kind = event["type"]
    if kind == "checks_register":
        return register(state, event)
    if kind == "check_setup":
        require(refactoring(state), "setup_not_planned", "Ordinary final project checks require an existing command or procedure")
        return setup(state, event)
    if kind in {"procedure_begin", "procedure_result"}:
        return procedure(state, event, directory)
    require(kind == "check_run", "check_operation", "Unsupported run-level check operation")
    return run(state, event, directory)


def progress(state):
    from .state import execution_directory
    required = (set(criteria(state)) if refactoring(state) else
                {criterion for check in registry(state)["checks"] for criterion in check["criteria"]})
    confirmed, gaps = set(), []
    try:
        ready(state)
        _, matches, gaps = evidence(state, execution_directory(state["basis"]))
        failed = {criterion for gap in gaps for criterion in gap["criteria"]}
        confirmed = {criterion for item in matches for criterion in item["criteria"]} - failed
    except ValueError as exc:
        gaps = [{"reason": str(exc), "criteria": sorted(required)}]
    return {"confirmed_criteria": sorted(confirmed & required), "total_criteria": len(required),
            "gaps": gaps, "retired_checks": retired(state)}
