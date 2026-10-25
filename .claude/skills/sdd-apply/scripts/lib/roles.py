"""Host-attested fresh contexts and separate implementation/review results."""
from .common import digest, now, require, write_json
from .verification import current, independent, valid_evidence, local_criteria
from .review_policy import proven
from .candidates import reference, same
import re
from . import artifact_storage as artifacts
from pathlib import Path


def refactoring_context(state, task):
    from .inputs import basis_dependency, spec_modules
    root = Path(state["basis"]["change_root"])
    design = spec_modules(basis_dependency(state["basis"])).read_document(root / "design.md", "refactoring")
    criteria = local_criteria(state, task) | set(task["plan"]["contributes_to"])
    decisions = {change.get("decision") for change in task["plan"].get("test_changes", [])}
    registry = task.get("check_registry")
    baseline = task.get("baseline_checks")
    baseline_event = next((entry for entry in reversed(state["events"])
                           if entry["event"]["task_id"] == task["plan"]["id"]
                           and entry["event"]["type"] == "check_run"
                           and entry["event"]["payload"].get("stage") == "baseline"), None)
    return {"scope": task["plan"]["scope"],
            "acceptance": [record for record in state["acceptance"].values() if record["task"] == task["plan"]["id"]],
            "preserves": task["plan"]["preserves"], "contributes_to": task["plan"]["contributes_to"],
            "preservation_reason": task["plan"].get("preservation_reason"),
            "test_changes": task["plan"].get("test_changes", []),
            "design": [record for record in design.records if record.get("id") in criteria | decisions
                       or record["sdd_record"] == "decision" and criteria & set(record.get("criteria", []))],
            "sources": {name: str(root / name) for name in ("proposal.md", "design.md", "tasks.md")},
            "check_registry": {"revision": registry["revision"], "history": [
                {key: entry[key] for key in ("revision", "event_id", "operation")} | {"checks_hash": digest(entry["checks"])}
                for entry in registry["history"]]} if registry else None,
            "baseline": {"role_id": baseline["role_id"], "registry_revision": baseline["registry_revision"],
                         "log": baseline_event["result"]["log"] if baseline_event else None,
                         "outputs": [{key: output[key] for key in ("check_id", "outcome", "command", "exit_code") if key in output}
                                     for output in baseline["outputs"]]} if baseline else None,
            "whole_result": "contributes_to records scope of contribution; local acceptance does not prove the whole result"}


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task required")
    p, kind = event["payload"], event["type"]
    if kind == "role_register":
        require(set(p) >= {"role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"}, "role_schema", "Host context and launch evidence required")
        require(p["kind"] in {"executor", "verifier", "reviewer", "final_verifier"} and p["fresh"] is True, "fresh_role", "A fresh context is mandatory")
        require(p["host"] in {"codex", "claude-code"} and p["launch_ref"] and p["context_id"], "host_evidence", "Record actual host launch; do not simulate a role")
        require(p["role_id"] not in state["roles"], "duplicate_role", "Role already registered")
        require(isinstance(p["role_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", p["role_id"]), "role_id", "Use a filesystem-safe role ID")
        require(p["context_id"] != state["owner"], "orchestrator_role", "Use a separate context")
        from .subagents import resolver
        selection = p.get("agent_selection")
        configuration = resolver(state)
        _, settings_source, _ = configuration.settings(Path(state["basis"]["project_root"]))
        require(selection is not None or settings_source is None, "agent_selection_missing",
                "Resolve the role from project settings before launching and registering it")
        if selection is not None:
            configuration.validate_selection(selection, state["basis"]["project_root"],
                                             "sdd-apply." + p["kind"], p["host"])
        if p["kind"] == "executor":
            require(not any(state["roles"][r]["kind"] == "executor" and state["roles"][r]["status"] == "active" for r in task["roles"]), "writer_active", "Finish or reconcile the previous executor before assigning another")
        for role in state["roles"].values():
            if role["context_id"] == p["context_id"]:
                require(role["task_id"] == task["plan"]["id"] and role["kind"] in {"reviewer", "verifier"} and p["kind"] in {"reviewer", "verifier"}, "context_reused", "Only verifier/reviewer of the same task may share a fresh context")
                previous = role.get("agent_selection")
                if selection is not None or previous is not None:
                    require(selection is not None and previous is not None
                            and selection["mode"] != "native-agent" and previous["mode"] != "native-agent"
                            and configuration.launch_identity(selection) == configuration.launch_identity(previous),
                            "agent_selection_conflict", "Different agent selections require separate fresh contexts")
        require(p["capabilities"].get("fresh_context") is True, "host_limits", "Fresh context mechanism unavailable; distinguish busy slots from unsupported host")
        role = {**p, "task_id": task["plan"]["id"], "status": "active", "registered_at": now()}
        state["roles"][p["role_id"]] = role
        task["roles"].append(p["role_id"])
        packet = {"task": task["plan"], "basis": state["basis"]["manifest"], "project_root": state["basis"]["project_root"], "execution_directory": str(directory), "paths": task["paths"], "worktree": task["worktree"], "candidate": reference(state, task["candidate"]), "checks": task["checks"], "prior_commits": [{**commit, "candidate": reference(state, commit["candidate"])} for commit in task["commits"]], "blockers": task["blockers"], "rejected_approaches": task.get("rejected_approaches", []), "role": role}
        if state["basis"].get("work_kind", "change") == "refactoring":
            packet["work_kind"] = "refactoring"
            packet["refactoring"] = refactoring_context(state, task)
        if task["worktree"]:
            packet["worktree"] = {key: value for key, value in task["worktree"].items()
                                  if key not in {"snapshot", "inventory"}}
            packet["worktree_state"] = {"path": "state.json", "task_id": task["plan"]["id"]}
        import json
        for effect in artifacts.paths(directory / "runs" / state["run_id"] / "effects", "*.json"):
            record = json.loads(artifacts.read_text(effect))
            if (record["phase"] == "prepared" and record["request"]["operation"] == "worktree_refresh"
                    and record["request"]["task_id"] == task["plan"]["id"]):
                saved = record["request"]["precondition"]
                packet["worktree_recovery"] = {"intent_id": record["request"]["event"]["event_id"],
                    "source": saved["old"]["path"], "replacement": saved["new"],
                    "patch": str(artifacts.contained(saved["artifacts"], "task.patch"))}
        path = artifacts.contained(directory, f"runs/{state['run_id']}/roles/{p['role_id']}.json")
        write_json(path, packet)
        return {"role": role, "packet": str(path)}
    if kind == "role_result":
        role = state["roles"].get(p.get("role_id"))
        require(role and role["task_id"] == task["plan"]["id"] and role["status"] == "active", "role_missing", "Active registered role required")
        require(p.get("result") and p.get("trace"), "role_result", "Result and host trace required")
        role.update(status="finished", result=p["result"], trace=p["trace"])
        # Executor DONE is deliberately only a role result.
        return {"role_finished": p["role_id"], "task_status": task["status"]}
    if kind == "review_start":
        require(task["status"] in {"verifying", "reviewing", "integrating"}, "review_phase", "Verification precedes review")
        independent(state, task, p.get("role_id"), {"reviewer"})
        valid_evidence(state, task, directory, "integration" if task.get("worktree", {}) and task["worktree"].get("integrated") else None)
        from .budgets import reserve_review
        if not reserve_review(state, task, event["event_id"]):
            return {"blocked": "review_limit_reached"}
        task["active_reviewer"] = p["role_id"]
        task["status"] = "reviewing"
        return {"round": task["review_rounds_started"], "candidate": reference(state, task["candidate"])}
    require(kind == "review_result", "role_operation", kind)
    require(task["active_review"] and task.get("active_reviewer") == p.get("role_id"), "review_not_started", "Reserve review round first")
    independent(state, task, p["role_id"], {"reviewer"})
    current(state, task)
    require(same(state, p.get("candidate"), task["candidate"]), "stale_review", "Review must name the frozen candidate")
    require(p.get("verdict") in {"pass", "changes", "more_checks"} and isinstance(p.get("findings"), list), "review_schema", "Verdict and findings required")
    require(p.get("test_integrity") and p.get("trace"), "review_evidence", "Review assertions, skips/xfail and command weakening; retain trace")
    findings = []
    for finding in p["findings"]:
        require(isinstance(finding, dict), "finding_schema", "Finding must be an object")
        require(set(finding) >= {"severity", "criteria", "path", "problem", "resolution"}, "finding_schema", "Findings need AC, file and resolution condition")
        require(finding["severity"] in {"blocker", "recommendation"}, "finding_severity", "Unknown severity")
        findings.append({**finding, "reported_severity": finding["severity"],
                         "severity": "blocker" if proven(finding) else "recommendation"})
    blockers = any(f["severity"] == "blocker" for f in findings)
    require(p["verdict"] != "pass" or not blockers, "review_blocker", "Pass conflicts with proven violations")
    verdict = "pass" if p["verdict"] == "changes" and not blockers else p["verdict"]
    result = {**p, "verdict": verdict, "reported_verdict": p["verdict"], "findings": findings,
              "round_id": task["active_review"], "round": task["review_rounds_started"]}
    task["reviews"].append(result)
    task["review_rounds_completed"] += 1
    task["active_review"] = None
    state["roles"][p["role_id"]]["status"] = "finished"
    if verdict == "pass":
        task["status"] = "integrating" if task["worktree"] and not task["worktree"].get("integrated") else "committing"
    elif verdict == "more_checks":
        task["status"] = "verifying"
    else:
        from .budgets import failure
        failure(state, task, "review", "changes_requested")
    return {"verdict": verdict, "status": task["status"]}
