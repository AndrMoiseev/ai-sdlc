"""Exact command registry and independently produced, commit-bound evidence."""
from .repository import repository
import json
from pathlib import Path
from copy import deepcopy
from .common import contained, digest, now, require, write_json
from .state import snapshot, clean_source
from .inputs import spec_modules
from .check_registry import selected, require_new_ids
from . import artifact_storage as artifacts
from . import check_evidence
from . import explorer_assignments as explorer

check_runner = spec_modules("check_runner")


def local_criteria(state, task):
    """A contribution never substitutes for a task's acceptance contract."""
    if state["basis"].get("work_kind", "change") != "refactoring":
        return set(task["plan"]["covers"])
    local = {record["id"] for record in state["acceptance"].values()
             if record["task"] == task["plan"]["id"]}
    return local | set(task["plan"]["preserves"])


def record_registry(state, task, event):
    """Append snapshots; callers must authorize each mutation before recording it."""
    registry = task.setdefault("check_registry", {"revision": 0, "confirmed_revision": 0, "history": []})
    registry["revision"] += 1
    registry["history"].append({"revision": registry["revision"], "event_id": event["event_id"],
                                "operation": event["type"], "checks": deepcopy(task["checks"])})
    if registry.get("transition"):
        registry["history"][-1]["transition"] = deepcopy(registry["transition"])


def registry_current(state, task):
    if state["basis"].get("work_kind", "change") != "refactoring":
        return
    registry = task.get("check_registry", {})
    history = registry.get("history", [])
    require(history and registry.get("revision") == len(history)
            and [item["revision"] for item in history] == list(range(1, len(history) + 1))
            and history[-1]["checks"] == task["checks"], "registry_changed",
            "Verification registry changed without an authorized revision")
    from .check_registry import validate
    validate(task)
    allowed = local_criteria(state, task)
    covered = {criterion for check in task["checks"] for criterion in check["criteria"]}
    require(allowed <= covered, "criteria_uncovered", "Local acceptance and preservation checks remain mandatory")


def root_for(state, task):
    return task["worktree"]["path"] if task.get("worktree") and not task["worktree"].get("integrated") else state["basis"]["project_root"]


def current(state, task):
    require(task["status"] in {"verifying", "reviewing", "integrating", "committing", "accepted"},
            "check_phase", "Prepare the task commit before verification")
    registry_current(state, task)
    if state["basis"].get("work_kind", "change") == "refactoring":
        require(task.get("baseline_checks"), "baseline_missing", "Capture existing checks before freezing a refactoring result")
    source = snapshot(state, root_for(state, task))
    clean_source(source)
    return source


def independent(state, task, role_id, kinds):
    role = state["roles"].get(role_id)
    if state["basis"].get("work_kind") == "refactoring" and role and role["kind"] == "final_verifier":
        require(False, "final_role", "Refactoring final verification uses task_id=null and the whole applicable registry")
    require(role and role["kind"] in kinds and role["task_id"] == task["plan"]["id"] and role["status"] == "active", "role_unavailable", "Active independent role required")
    authors = [state["roles"][r]["context_id"] for r in task["roles"] if state["roles"][r]["kind"] == "executor"]
    require(role["context_id"] not in authors and role["fresh"] is True, "role_not_independent", "Author context cannot independently verify or review")
    return role


def valid_evidence(state, task, directory, stage=None):
    if stage != "final":
        source = current(state, task)
    else:
        source = snapshot(state, root_for(state, task))
    checks = selected(state, task, final=stage == "final")
    required = {check["id"] for check in checks}
    if state["basis"].get("work_kind", "change") != "refactoring":
        recorded = {item["check_id"] for item in task["evidence"]
                    if item["stage"] in ({stage} if stage else {"independent", "integration"})}
        require(required and required <= recorded, "required_checks", "Every required command/procedure must pass")
    matches, seen, validated = [], set(), set()
    for item in reversed(task["evidence"]):
        if item.get("procedure"):
            continue
        if item["stage"] not in ({stage} if stage else {"independent", "integration"}):
            continue
        if item["check_id"] in seen:
            continue
        seen.add(item["check_id"])
        require(item["outcome"] == "passed", "required_checks", "Latest required check is failed, unavailable or stale")
        path = artifacts.contained(directory, item["log"])
        require(artifacts.is_file(path), "evidence_corrupt", item["log"])
        raw = artifacts.read_bytes(path)
        require(digest(raw) == item["log_hash"], "evidence_corrupt", item["log"])
        log_data = json.loads(raw)
        evidence_run_id = None
        if not item.get("procedure"):
            require(log_data.get("task_id") == task["plan"]["id"]
                    and log_data.get("role_id") == item["role_id"]
                    and log_data.get("stage") == item["stage"]
                    and log_data.get("after") == log_data.get("before")
                    and log_data.get("before", {}).get("commit") == item.get("head"),
                    "evidence_basis", "Evidence must name this task and its unchanged recorded source")
            if stage == "final":
                if log_data.get("run_id") == state["run_id"]:
                    require(log_data.get("before") == source, "evidence_basis",
                            "Current-run final evidence must name the current source")
                evidence_run_id = check_evidence.historical_context(state, task, log_data, item, directory)
            else:
                require(log_data.get("run_id") == state["run_id"] and log_data.get("before") == source,
                        "evidence_basis", "Evidence must name the current run and source")
        if state["basis"].get("work_kind", "change") == "refactoring" and not item.get("procedure"):
            require(log_data.get("work_kind") == "refactoring"
                    and log_data.get("run_id") == state["run_id"]
                    and log_data.get("task_id") == task["plan"]["id"]
                    and log_data.get("stage") == item["stage"]
                    and log_data.get("role_id") == item["role_id"]
                    and log_data.get("registry_revision") == task["check_registry"]["revision"]
                    and log_data.get("registered_checks") == checks,
                    "evidence_basis", "Evidence must name this task and registry revision")
            check = next((check for check in checks if check["id"] == item["check_id"]), None)
            output = next((output for output in log_data.get("outputs", []) if output.get("check_id") == item["check_id"]), None)
            require(check and output and output["outcome"] == item["outcome"], "evidence_basis", "Evidence must contain its registered check")
            run = check["setup"] or check["run"]
            if "command" in run and explorer.execution_kind(check) == "deterministic":
                require(output.get("command") == run["command"] and output.get("exit_code") == 0
                        and output.get("criteria") == check["criteria"], "evidence_command",
                        "An unrelated successful command cannot establish a registered criterion")
        if not item.get("procedure") and item["log_hash"] not in validated:
            check_evidence.validate(state, log_data, checks, directory, expected_run_id=evidence_run_id)
            validated.add(item["log_hash"])
        check = next((check for check in checks if check["id"] == item["check_id"]), None)
        if check and ("procedure" in (check["setup"] or check["run"]) or explorer.execution_kind(check) != "deterministic"):
            latest = procedure_evidence(state, task, check, item["stage"], log_data["before"], directory)
            output = next((value for value in log_data["outputs"] if value["check_id"] == check["id"]), {})
            require(latest["outcome"] == "passed" and all(output.get(key) == latest.get(key)
                    for key in ("procedure_log", "procedure_log_hash")), "required_checks",
                    "The latest procedure must pass and be included in the current complete check run")
        for output in log_data.get("outputs", []):
            if output.get("procedure_log"):
                linked = artifacts.contained(directory, output["procedure_log"])
                require(artifacts.is_file(linked) and digest(artifacts.read_bytes(linked)) == output["procedure_log_hash"], "evidence_corrupt", "Procedure log changed")
        require(item["role_id"] in state["roles"], "unknown_role", "Evidence role missing")
        role = state["roles"][item["role_id"]]
        if not item.get("procedure"):
            explorer.authorize(state, task, item["role_id"], item["stage"], active=False, current_basis=False)
        authors = {r["context_id"] for r in state["roles"].values() if r["kind"] == "executor" and (stage == "final" or r["task_id"] == task["plan"]["id"])}
        require(role["context_id"] not in authors and role["fresh"], "role_not_independent", "Evidence author is not independent")
        matches.append(item)
    require(required and required <= {m["check_id"] for m in matches}, "required_checks", "Every required command/procedure must pass")
    return matches


def require_command(command):
    require(check_runner.valid_command(command), "command_format", check_runner.COMMAND_FORMAT)


def procedure_evidence(state, task, check, stage, before, directory):
    if check["id"] in task.get("procedures", {}):
        return {"outcome": "unavailable", "description": "procedure_pending"}
    latest = next((e for e in reversed(task["evidence"]) if e["check_id"] == check["id"]
                   and e["stage"] == stage and e.get("procedure")), None)
    if not latest:
        return {"outcome": "unavailable", "description": "procedure_missing"}
    path = artifacts.contained(directory, latest["log"])
    require(artifacts.is_file(path) and digest(artifacts.read_bytes(path)) == latest["log_hash"],
            "evidence_corrupt", "Procedure evidence changed")
    record = json.loads(artifacts.read_bytes(path))
    require(record.get("check_id") == check["id"] and record.get("role_id") == latest["role_id"]
            and record.get("stage") == stage and record.get("outcome") == latest["outcome"],
            "evidence_basis", "Procedure evidence must name its exact check, role, stage and outcome")
    explorer.procedure_role(state, task, latest["role_id"], stage, check, active=False, current_basis=False)
    unchanged = record["before"] == before == record["after"] and record.get("registered_check") == check
    return {"outcome": latest["outcome"] if unchanged else "stale", "procedure_log": latest["log"],
            "procedure_log_hash": latest["log_hash"]}


def transition(state, task, event, directory):
    if task is None:
        from .final_checks import transition as whole
        return whole(state, event, directory)
    require(task is not None, "task_required", "Task required")
    kind, p = event["type"], event["payload"]
    if kind == "checks_revise":
        from .check_registry import revise
        return revise(state, task, event)
    if kind == "checks_register":
        require(task["status"] == "pending" and not task["checks"], "registry_frozen", "Register once before execution")
        checks = []
        for i, planned in enumerate(task["plan"]["verification"]):
            ident = (task["plan"]["id"] + "/" + planned["id"]
                     if state["basis"].get("work_kind", "change") == "refactoring" else f"plan-{i + 1}")
            checks.append({"id": ident, "criteria": planned["criteria"], "source": "tasks.md", "location": planned["location"], "run": planned["run"], "cwd": ".", "configuration": {}, "setup": None,
                           **({"execution_kind": planned["execution_kind"]} if "execution_kind" in planned else {})})
        require(p.get("inventory") and set(p["inventory"]) == {"instructions", "ci"}, "inventory_required", "Record inspected project instruction and CI files, including an explicit empty inventory")
        for check in p.get("additional", []):
            require(check.get("id") and check.get("source") and check.get("run"), "check_schema", "Additional required checks need ID, source and exact run")
            checks.append({**check, "setup": None, "cwd": check.get("cwd", "."), "configuration": check.get("configuration", {})})
        require(len({c["id"] for c in checks}) == len(checks), "duplicate_check", "Duplicate check ID")
        for check in checks:
            require(isinstance(check["run"], dict) and set(check["run"]) in ({"command"}, {"procedure"}, {"setup_required"}),
                    "check_schema", "run requires one command, procedure or setup_required key")
            explorer.execution_kind(check)
            if state["basis"].get("work_kind", "change") == "refactoring":
                require(check.get("criteria") and set(check["criteria"]) <= local_criteria(state, task),
                        "check_schema", "Bind checks to local acceptance or preserved criteria")
            if "command" in check["run"]:
                require_command(check["run"]["command"])
        require_new_ids(state, task, checks)
        task["checks"], task["inventory"] = checks, p["inventory"]
        record_registry(state, task, event)
        registry_current(state, task)
        return {"checks": checks}
    if kind == "checks_extend":
        require(task["status"] == "verifying" and not task["active_review"],
                "extension_phase", "Extend checks before review or after reviewer more_checks")
        current(state, task)
        additions = p.get("additional", [])
        require(bool(p.get("verification_result")) != bool(p.get("review_round")),
                "extension_evidence", "Reference either a verifier conclusion or reviewer more_checks round")
        if p.get("verification_result"):
            from .verification_results import extension
            extension(state, task, p, directory)
        else:
            require(task["reviews"] and task["reviews"][-1]["verdict"] == "more_checks"
                    and additions and p.get("review_round") == task["reviews"][-1]["round_id"],
                    "extension_evidence", "Reference the review requesting additional checks")
        require_new_ids(state, task, additions)
        for check in additions:
            require(isinstance(check, dict) and check.get("id") and check.get("source")
                    and isinstance(check.get("run"), dict) and set(check["run"]) in ({"command"}, {"procedure"})
                    and isinstance(check.get("criteria"), list) and check["criteria"]
                    and all(isinstance(item, str) for item in check["criteria"])
                    and set(check["criteria"]) <= local_criteria(state, task),
                    "check_schema", "Add exact runnable checks with scoped AC")
            require(check["id"] not in {c["id"] for c in task["checks"]}, "duplicate_check", "Existing checks cannot be replaced")
            explorer.execution_kind(check)
            if "command" in check["run"]:
                require_command(check["run"]["command"])
            else:
                procedure = check["run"]["procedure"]
                require(isinstance(procedure, str) and procedure.strip(), "check_schema", "Procedure path required")
                require(contained(root_for(state, task), procedure).is_file(), "procedure_unavailable", procedure)
            task["checks"].append({**check, "setup": None, "cwd": check.get("cwd", "."), "configuration": check.get("configuration", {})})
        record_registry(state, task, event)
        return {"checks": task["checks"]}
    if kind == "check_setup":
        registry_current(state, task)
        check = next((c for c in task["checks"] if c["id"] == p.get("check_id")), None)
        require(check and ("setup_required" in check["run"] or "procedure" in check["run"]) and check["setup"] is None, "setup_not_planned", "Only planned, unresolved setup or procedure may be registered")
        require("setup_required" in check["run"] or explorer.execution_kind(check) == "deterministic",
                "setup_not_planned", "A semantic procedure cannot be replaced with a deterministic command")
        require(task["status"] in {"running", "repairing"}, "setup_phase", "Prepare checks within their task")
        require(p.get("command") and p.get("description") and task.get("baseline_checks"), "setup_evidence", "Need baseline check inventory and preparation description")
        require_command(p["command"])
        check["setup"] = {"command": p["command"], "cwd": p.get("cwd", "."), "configuration": p.get("configuration", {}), "description": p["description"], "before": task["start_snapshot"], "after": snapshot(state, root_for(state, task))}
        record_registry(state, task, event)
        return {"setup": check}
    if kind == "candidate":
        require(task["status"] in {"running", "repairing", "integrating"}, "candidate_phase", "Candidate requires completed implementation or integration")
        require(task.get("executor") and state["roles"][task["executor"]]["status"] == "finished", "writer_active", "Executor must finish writing before freezing")
        require(not any(state["roles"][r]["kind"] == "executor" and state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "All task writers must stop before freezing")
        require(all("setup_required" not in c["run"] or c["setup"] for c in task["checks"]), "setup_pending", "Resolve all planned setup")
        from .commits import freeze
        registry_current(state, task)
        if state["basis"].get("work_kind", "change") == "refactoring":
            require(task.get("baseline_checks"), "baseline_missing", "Capture existing checks before preparing a refactoring result")
        freeze(state, task, event, directory)
        task["status"] = "verifying"
        return {"commit": task["candidate_commit"]}
    if kind == "procedure_begin":
        registry_current(state, task)
        stage = p.get("stage")
        require(stage in {"baseline", "self", "independent", "integration", "final"}, "procedure_stage", "Unknown stage")
        check = next((c for c in selected(state, task, final=stage == "final") if c["id"] == p.get("check_id")), None)
        require(check and ("procedure" in check["run"] and not check["setup"]
                          or explorer.execution_kind(check) != "deterministic"),
                "procedure_check", "Use the registered procedure without replacing it")
        role = explorer.procedure_role(state, task, p.get("role_id"), stage, check)
        require(not task.get("last_check_failed") or task["active_repair"], "repair_cycle_required", "A retry after failure must reserve a repair cycle")
        previous = next((item for item in reversed(task["evidence"]) if item.get("procedure")
                         and item["check_id"] == check["id"] and item["stage"] == stage), None)
        require(not previous or previous["outcome"] == "passed" or task["active_repair"],
                "repair_cycle_required", "A failed procedure retry must reserve a repair cycle")
        if stage not in {"baseline", "final"}:
            current(state, task)
        if stage != "baseline":
            require(not any(state["roles"][ident]["kind"] == "executor" and state["roles"][ident]["status"] == "active"
                            for ident in task["roles"]), "writer_active", "All authors must stop before procedure execution")
        if stage == "integration":
            require(task.get("worktree") and task["worktree"].get("integrated"), "check_phase", "Integration procedures require an integrated commit")
        if stage == "final":
            require(task["status"] == "accepted", "final_role", "Final checks require an accepted task")
        root = root_for(state, task)
        path = contained(root, check["run"]["procedure"]) if "procedure" in check["run"] else None
        require(path is None or path.is_file(), "procedure_unavailable", str(path))
        pending = task.setdefault("procedures", {})
        require(check["id"] not in pending, "procedure_active", "Finish the existing procedure attempt")
        before = snapshot(state, root)
        clean_source(before)
        if stage == "baseline":
            require(task.get("start_snapshot") and not task.get("baseline_checks") and before == task["start_snapshot"], "baseline_changed", "Capture baseline before implementation edits")
        budget = explorer.procedure_budget(state, task, role, check, p.get("timeout", 300))
        pending[check["id"]] = {"check_id": check["id"], "registered_check": deepcopy(check), "role_id": p["role_id"],
                               "stage": stage, "before": before, "path": str(path) if path else None, "started_at": now(), **budget}
        return pending[check["id"]]
    if kind == "procedure_result":
        pending = task.get("procedures", {}).get(p.get("check_id"))
        require(pending and p.get("role_id") == pending["role_id"], "procedure_owner", "Match the registered procedure attempt")
        explorer.procedure_role(state, task, p["role_id"], pending["stage"], pending["registered_check"], current_basis=False)
        require(p.get("outcome") in {"passed", "failed", "unavailable", "skipped", "unstable"} and p.get("steps") and p.get("trace"), "procedure_evidence", "Actual steps, outcome and host trace required")
        after = snapshot(state, root_for(state, task))
        outcome = explorer.procedure_outcome(pending, p["outcome"], after == pending["before"])
        relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/{event['event_id']}.json"
        record = {"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], **pending, "after": after, "steps": p["steps"], "trace": p["trace"], "outcome": outcome, "reported_outcome": p["outcome"]}
        if pending.get("check_deadline", {}).get("expires", float("inf")) <= explorer.time.time():
            record["limitation"] = "check_deadline"
        path = artifacts.contained(directory, relative)
        write_json(path, record)
        item = {"check_id": p["check_id"], "stage": pending["stage"], "role_id": p["role_id"], "outcome": outcome, "log": relative, "log_hash": digest(artifacts.read_bytes(path)), "time": now(), "head": repository(root_for(state, task)).head(), "procedure": True}
        task["evidence"].append(item)
        del task["procedures"][p["check_id"]]
        return item
    require(kind == "check_run", "check_operation", kind)
    stage = p.get("stage")
    registry_current(state, task)
    require(stage in {"baseline", "self", "independent", "integration", "final"}, "check_stage", "Unknown verification stage")
    role_id = p.get("role_id")
    role = explorer.authorize(state, task, role_id, stage)
    before = None
    if stage in {"self", "independent", "integration", "final"}:
        require(task["status"] in {"verifying", "reviewing", "accepted", "integrating"}, "check_phase", "No frozen candidate")
        if stage != "final":
            before = current(state, task)
        else:
            require(task["status"] == "accepted", "final_role", "Final explorer checks accepted tasks at final HEAD")
        if task.get("last_check_failed"):
            require(task["active_repair"], "repair_cycle_required", "A retry after failure must reserve a repair cycle")
        require(not any(state["roles"][ident]["kind"] == "executor" and state["roles"][ident]["status"] == "active"
                        for ident in task["roles"]), "writer_active", "All authors must stop before check execution")
        if stage == "integration":
            require(task.get("worktree") and task["worktree"].get("integrated"), "check_phase", "Integration checks require an integrated commit")
    require(task["checks"], "checks_missing", "Register verification first")
    root = Path(root_for(state, task))
    if stage == "self":
        before = current(state, task)
    if before is None:
        before = snapshot(state, root)
        clean_source(before)
    if stage == "baseline":
        require(task.get("start_snapshot") and not task.get("baseline_checks") and before == task["start_snapshot"], "baseline_changed", "Capture the initial checks before any implementation edits")
    deadline = explorer.attempt_deadline(state, task, role, p.get("timeout", 300))
    outputs = []
    locations = None
    checks = selected(state, task, final=stage == "final")
    for check in checks:
        if deadline.remaining() <= 0:
            outputs.append(explorer.expired(check))
            continue
        run = check["setup"] or check["run"]
        if stage == "baseline" and "setup_required" in run:
            outputs.append({"check_id": check["id"], "outcome": "planned_absence", "description": run["setup_required"]})
            continue
        if "location" in check:
            if locations is None:
                locations = spec_modules("paths")
            location = locations.verification_location(root, check["location"])
            if not (location.is_file() or location.is_dir()):
                outputs.append({"check_id": check["id"], "outcome": "unavailable", "description": "Required verification location is missing", "location": check["location"]})
                continue
        if "command" not in run or explorer.execution_kind(check) != "deterministic":
            if "procedure" in run or explorer.execution_kind(check) != "deterministic":
                outputs.append({"check_id": check["id"], **procedure_evidence(state, task, check, stage, before, directory)})
                continue
            outputs.append({"check_id": check["id"], "outcome": "unavailable", "description": "No executable command for required procedure"})
            continue
        relative = run.get("cwd", check["cwd"])
        cwd = root if relative == "." else contained(root, relative)
        result = check_runner.run_command(run["command"], cwd, deadline.remaining())
        result.update(check_id=check["id"], configuration=run.get("configuration", check["configuration"]), criteria=check["criteria"])
        result["_report_capture"] = check_evidence.capture_reports(result)
        if deadline.remaining() <= 0 and result["outcome"] == "passed":
            result.update(outcome="unavailable", limitation="check_deadline")
        outputs.append(result)
    after = snapshot(state, root)
    record = {"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], "task_id": task["plan"]["id"], "role_id": role_id, "stage": stage, "before": before, "after": after, "outputs": outputs}
    if state["basis"].get("work_kind", "change") == "refactoring":
        record.update(work_kind="refactoring", registry_revision=task["check_registry"]["revision"],
                      registered_checks=deepcopy(checks))
    relative = f"runs/{state['run_id']}/tasks/{task['plan']['id']}/{task['attempt']}/{event['event_id']}.json"
    path = artifacts.contained(directory, relative)
    summary = check_evidence.persist(state, record, checks, directory, event["event_id"])
    write_json(path, record)
    outcome = "passed" if all(r["outcome"] == "passed" for r in outputs) and before == after else "failed"
    if any(r["outcome"] == "unavailable" or not r["evidence_complete"] for r in outputs):
        outcome = "unavailable"
    if stage == "baseline":
        task["baseline_checks"] = record
        if all(r["outcome"] == "planned_absence" or r["outcome"] == "passed"
               and r["evidence_complete"] for r in outputs) and before == after:
            return {"outcome": "baseline_recorded", "log": relative, "summary": summary}
        state["status"] = "blocked"
        state["blockers"].append({"reason": "baseline_failed", "task_id": task["plan"]["id"], "resume_condition": "Resolve or explicitly scope the pre-existing failure", "log": relative})
    for result in outputs:
        task["evidence"].append({"check_id": result["check_id"], "stage": stage, "role_id": role_id, "outcome": (result["outcome"] if result["evidence_complete"] else "unavailable") if before == after else "stale", "log": relative, "log_hash": digest(artifacts.read_bytes(path)), "time": now(), "head": repository(root).head()})
    if stage != "self" or outcome != "passed":
        task["last_check_failed"] = outcome != "passed"
        if task["active_repair"] and outcome != "unavailable" and stage in {"independent", "integration", "final"}:
            task["repair_cycles"].append({"id": task["active_repair"], "outcome": outcome, "log": relative})
            task["active_repair"] = None
        if outcome != "passed":
            from .budgets import failure
            failure(state, task, "test", outcome)
    return {"outcome": outcome, "log": relative, "summary": summary}
