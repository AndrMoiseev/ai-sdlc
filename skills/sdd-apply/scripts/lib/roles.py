"""Host-attested fresh contexts and separate implementation/review results."""
from .common import digest, now, require, write_json
from .verification import current, independent, local_criteria, valid_evidence
from .verification_results import require_passed
from .review_policy import LENSES, proven, round_results, test_change_context
from .inputs import read_plan_document, document_paths
import re
from . import artifact_storage as artifacts
from pathlib import Path


def refactoring_context(state, task):
    root = Path(state["basis"]["change_root"])
    design = read_plan_document(state["basis"], "design.md")
    criteria = local_criteria(state, task) | set(task["plan"]["contributes_to"])
    for change in task["plan"].get("test_changes", []):
        criteria.update(change["criteria"])
        criteria.update(change.get("replacement_criteria", []))
    decisions = {change.get("decision") for change in task["plan"].get("test_changes", [])}
    registry = task.get("check_registry")
    baseline = task.get("baseline_checks")
    baseline_event = task.get("baseline_event")
    return {"scope": task["plan"]["scope"],
            "acceptance": [record for record in state["acceptance"].values() if record["task"] == task["plan"]["id"]],
            "preserves": task["plan"]["preserves"], "contributes_to": task["plan"]["contributes_to"],
            "preservation_reason": task["plan"].get("preservation_reason"),
            "test_changes": task["plan"].get("test_changes", []),
            "test_evolution": test_change_context(state, task),
            "design": [record for record in design if record.get("id") in criteria | decisions
                       or record["sdd_record"] == "decision" and criteria & set(record.get("criteria", []))],
            "sources": {name: str(root / name) for name in ("proposal.md", "design.md", "tasks.md")},
            "check_registry": {"revision": registry["revision"], "history": [
                {key: entry[key] for key in ("revision", "event_id", "operation")} | {"checks_hash": digest(entry["checks"])}
                for entry in registry["history"]]} if registry else None,
            "baseline": {"role_id": baseline["role_id"], "registry_revision": baseline["registry_revision"],
                         "log": baseline_event["log"] if baseline_event else None,
                         "outputs": [{key: output[key] for key in ("check_id", "outcome", "command", "exit_code") if key in output}
                                     for output in baseline["outputs"]]} if baseline else None,
            "whole_result": "contributes_to records scope of contribution; local acceptance does not prove the whole result"}


def transition(state, task, event, directory):
    p, kind = event["payload"], event["type"]
    from . import explorer_assignments as explorer
    registered = state["roles"].get(p.get("role_id"), {})
    research = task is None and ((kind == "role_register" and p.get("kind") == "explorer"
                                 and p.get("assignment", {}).get("kind") == "research")
                                or kind == "role_result" and registered.get("assignment", {}).get("kind") == "research")
    require(task is not None or research, "task_required", "Only research explorers use null task scope")
    task_id = task["plan"]["id"] if task else None
    if kind == "role_register":
        require(set(p) >= {"role_id", "kind", "context_id", "fresh", "host", "launch_ref", "capabilities"}, "role_schema", "Host context and launch evidence required")
        require(p["kind"] in {"executor", "reviewer", "explorer"}
                and p["fresh"] is True, "fresh_role", "A fresh context is mandatory")
        if p["kind"] == "reviewer":
            require(p.get("lens_id") in LENSES, "review_lens", "Assign exactly one required review lens")
        require(p["host"] in {"codex", "claude-code"} and p["launch_ref"] and p["context_id"], "host_evidence", "Record actual host launch; do not simulate a role")
        require(p["role_id"] not in state["roles"], "duplicate_role", "Role already registered")
        require(isinstance(p["role_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]+", p["role_id"]), "role_id", "Use a filesystem-safe role ID")
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
                continuation = (role["kind"] == p["kind"] == "explorer" and role["task_id"] == task_id
                                and role["status"] == "finished" and role["host"] == p["host"])
                require(continuation, "context_reused",
                        "Only completed explorer assignments of the same task may share a context; every reviewer starts fresh")
                previous = role.get("agent_selection")
                if selection is not None or previous is not None:
                    require(selection is not None and previous is not None
                            and configuration.launch_identity(selection) == configuration.launch_identity(previous),
                            "agent_selection_conflict", "Different agent selections require separate fresh contexts")
        require(p["capabilities"].get("fresh_context") is True, "host_limits", "Fresh context mechanism unavailable; distinguish busy slots from unsupported host")
        if p["kind"] == "explorer":
            explorer.validate(state, task, p)
        role = {**p, "task_id": task_id, "status": "active", "registered_at": now(),
                "registered_revision": state["revision"] + 1}
        state["roles"][p["role_id"]] = role
        if research:
            packet = {"task": None, "role": role, "assignment": role["assignment"],
                      "project_root": state["basis"]["project_root"], "execution_directory": str(directory),
                      "sources": {entry: str(Path(state["basis"]["change_root"]) / entry)
                                  for entry in document_paths(state["basis"])}}
            path = artifacts.contained(directory, f"runs/{state['run_id']}/roles/{p['role_id']}.json")
            write_json(path, packet)
            return {"role": role, "packet": str(path)}
        task["roles"].append(p["role_id"])
        packet = {"task": task["plan"], "project_root": state["basis"]["project_root"], "execution_directory": str(directory), "paths": task["paths"], "worktree": task["worktree"], "checks": task["checks"], "prior_commits": task["commits"], "blockers": task["blockers"], "rejected_approaches": task.get("rejected_approaches", []), "role": role}
        if p["kind"] == "explorer":
            packet["assignment"] = role["assignment"]
        if p["kind"] == "reviewer" and p["lens_id"] == "verification":
            from .verification_results import packet as verification_packet
            packet["verification"] = verification_packet(state, task, directory)
        if state["basis"].get("work_kind", "change") == "refactoring":
            packet["work_kind"] = "refactoring"
            packet["refactoring"] = refactoring_context(state, task)
        packet["sources"] = {entry: str(Path(state["basis"]["change_root"]) / entry)
                             for entry in document_paths(state["basis"])}
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
                    "patch": saved["patch"] if "patch" in saved else str(artifacts.contained(saved["artifacts"], "task.patch"))}
        path = artifacts.contained(directory, f"runs/{state['run_id']}/roles/{p['role_id']}.json")
        write_json(path, packet)
        return {"role": role, "packet": str(path)}
    if kind == "role_result":
        role = state["roles"].get(p.get("role_id"))
        require(role and role["task_id"] == task_id and role["status"] == "active", "role_missing", "Active registered role required")
        require(p.get("result") and p.get("trace"), "role_result", "Result and host trace required")
        if role["kind"] == "explorer" and role["assignment"]["kind"] == "research":
            explorer.research_result(p["result"])
        role.update(status="finished", result=p["result"], trace=p["trace"])
        # Executor DONE is deliberately only a role result.
        return {"role_finished": p["role_id"], "task_status": task["status"] if task else None}
    if kind == "review_start":
        require(task["status"] in {"verifying", "reviewing", "integrating"}, "review_phase", "Verification precedes review")
        role = independent(state, task, p.get("role_id"), {"reviewer"})
        valid_evidence(state, task, directory)
        lens = role["lens_id"]
        from .verification_results import attempts, stage_for
        basis = {"checks": explorer.basis(state, task, "checks", stage_for(task)),
                 "attempts_hash": digest(attempts(task, stage_for(task)))}
        from .budgets import reserve_review
        if task["active_review"]:
            require(task["review_basis"] == basis, "review_stale", "Review lenses require the same check run and source")
            require(lens not in task["active_reviewers"], "review_active", "Resume the existing review lens instead of reserving twice")
        else:
            if not reserve_review(state, task, event["event_id"]):
                return {"blocked": "review_limit_reached"}
            task["active_reviewers"] = {}
            task["review_basis"] = basis
        task["active_reviewers"][lens] = p["role_id"]
        task["status"] = "reviewing"
        return {"round": task["review_rounds_started"], "lens_id": lens}
    require(kind == "review_result", "role_operation", kind)
    role = independent(state, task, p.get("role_id"), {"reviewer"})
    lens = role["lens_id"]
    require(task["active_review"] and task.get("active_reviewers", {}).get(lens) == p.get("role_id"), "review_not_started", "Reserve this review lens first")
    current(state, task)
    from .verification_results import attempts, stage_for
    require(task["review_basis"] == {"checks": explorer.basis(state, task, "checks", stage_for(task)),
            "attempts_hash": digest(attempts(task, stage_for(task)))},
            "review_stale", "Source, registry or check run changed during review")
    require("candidate" not in p, "review_schema", "Review results no longer accept candidate references")
    require(p.get("verdict") in {"pass", "changes", "more_checks"} and isinstance(p.get("findings"), list), "review_schema", "Verdict and findings required")
    require(p.get("trace"), "review_evidence", "Retain the actual reviewer trace")
    if lens == "verification":
        require(p.get("test_integrity"), "review_evidence", "Verification owns assertion strength and test integrity")
        from .verification_results import applicable
        conclusion = applicable(state, task, directory)
        require(conclusion["role_id"] == p["role_id"] and conclusion["round_id"] == task["active_review"],
                "verification_missing", "Submit this lens's current criterion conclusion")
        require(p["verdict"] != "pass" or conclusion["outcome"] == "passed",
                "verification_failed", "Unconfirmed criteria prevent a passing verification lens")
    else:
        require("test_integrity" not in p and p["verdict"] != "more_checks", "review_scope",
                "Code review owns architecture and code quality; route test evidence gaps to verification")
    findings = []
    for finding in p["findings"]:
        require(isinstance(finding, dict), "finding_schema", "Finding must be an object")
        require(set(finding) >= {"severity", "criteria", "path", "problem", "resolution"}, "finding_schema", "Findings need AC, file and resolution condition")
        require(finding["severity"] in {"blocker", "recommendation"}, "finding_severity", "Unknown severity")
        proof_kind = finding.get("proof", {}).get("kind") if isinstance(finding.get("proof"), dict) else None
        require(not (lens == "code" and (proof_kind == "acceptance" or finding["criteria"]))
                and not (lens == "verification" and proof_kind == "architecture"),
                "review_scope", "Acceptance and test evidence belong to verification; architecture belongs to code")
        findings.append({**finding, "reported_severity": finding["severity"],
                         "severity": "blocker" if proven(finding) else "recommendation"})
    blockers = any(f["severity"] == "blocker" for f in findings)
    require(p["verdict"] != "pass" or not blockers, "review_blocker", "Pass conflicts with proven violations")
    verdict = ("pass" if p["verdict"] == "changes" and not blockers
               and (lens == "code" or conclusion["outcome"] == "passed") else p["verdict"])
    result = {**p, "lens_id": lens, "verdict": verdict, "reported_verdict": p["verdict"], "findings": findings,
              "round_id": task["active_review"], "round": task["review_rounds_started"]}
    task["reviews"].append(result)
    state["roles"][p["role_id"]]["status"] = "finished"
    results = round_results(task)
    if set(results) != set(LENSES):
        return {"verdict": verdict, "status": "reviewing", "pending_lenses": sorted(set(LENSES) - set(results))}
    verdicts = {review["verdict"] for review in results.values()}
    verdict = "changes" if "changes" in verdicts else "more_checks" if "more_checks" in verdicts else "pass"
    if verdict == "pass":
        require_passed(state, task, directory)
    task["review_rounds_completed"] += 1
    task["active_review"] = None
    if verdict == "pass":
        task["status"] = "integrating" if task["worktree"] and not task["worktree"].get("integrated") else "committing"
    elif verdict == "more_checks":
        task["status"] = "verifying"
    else:
        from .budgets import failure
        failure(state, task, "review", "changes_requested")
    return {"verdict": verdict, "status": task["status"]}
