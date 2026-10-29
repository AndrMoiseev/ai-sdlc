"""Independent criterion conclusions tied to exact current execution evidence."""
from copy import deepcopy
import json

from . import artifact_storage as artifacts
from .common import digest, now, require
from .explorer_assignments import basis
from .verification import current, independent, local_criteria, valid_evidence


def stage_for(task):
    return "integration" if task.get("worktree") and task["worktree"].get("integrated") else "independent"


def attempts(task, stage):
    # Include procedure attempts and pending procedures: a newer unfinished or
    # failed procedure must invalidate a conclusion about its previous aggregate.
    return {"evidence": [item for item in task["evidence"] if item["stage"] == stage],
            "procedures": {key: value for key, value in task.get("procedures", {}).items()
                           if value["stage"] == stage}}


def evidence_refs(task, stage, directory):
    latest = {}
    for item in task["evidence"]:
        if item["stage"] == stage and not item.get("procedure"):
            latest[item["check_id"]] = item
    refs = []
    for check_id, item in sorted(latest.items()):
        path = artifacts.contained(directory, item["log"])
        require(artifacts.is_file(path), "evidence_missing", item["log"])
        raw = artifacts.read_bytes(path)
        require(digest(raw) == item["log_hash"], "evidence_corrupt", item["log"])
        record = json.loads(raw)
        refs.append({"check_id": check_id, "log": item["log"], "sha256": item["log_hash"],
                     "check_run_id": record.get("check_run_id"), "summary": record.get("summary")})
    return refs


def packet(state, task, directory):
    stage = stage_for(task)
    return {"stage": stage, "basis": basis(state, task, "checks", stage),
            "criteria": sorted(local_criteria(state, task)),
            "evidence_refs": evidence_refs(task, stage, directory)}


def validate_refs(state, task, stage, refs, directory):
    from .check_evidence import validate
    from .check_registry import selected
    checks = selected(state, task)
    source = current(state, task)
    validated = set()
    for ref in refs:
        if ref["log"] in validated:
            continue
        record = json.loads(artifacts.read_bytes(artifacts.contained(directory, ref["log"])))
        require(record.get("run_id") == state["run_id"] and record.get("task_id") == task["plan"]["id"]
                and record.get("stage") == stage and record.get("before") == source == record.get("after"),
                "verification_basis", "Conclusion evidence must belong to this task, stage and unchanged source")
        from .explorer_assignments import authorize
        role = authorize(state, task, record.get("role_id"), stage, active=False)
        authors = {state["roles"][ident]["context_id"] for ident in task["roles"]
                   if state["roles"][ident]["kind"] == "executor"}
        require(role["fresh"] is True and role["context_id"] not in authors,
                "role_not_independent", "Conclusion evidence must come from an independent explorer")
        validate(state, record, checks, directory, require_complete=False)
        for output in record["outputs"]:
            if output.get("procedure_log"):
                path = artifacts.contained(directory, output["procedure_log"])
                require(artifacts.is_file(path) and digest(artifacts.read_bytes(path)) == output["procedure_log_hash"],
                        "evidence_corrupt", "Referenced procedure evidence changed")
        validated.add(ref["log"])


def applicable(state, task, directory, stage=None):
    stage = stage or stage_for(task)
    results = task.get("verification_results", [])
    result = next((item for item in reversed(results) if item["stage"] == stage), None)
    require(result is not None, "verification_missing", "A current verifier conclusion is required")
    current(state, task)
    require(result["basis"] == basis(state, task, "checks", stage)
            and result["attempts_hash"] == digest(attempts(task, stage)),
            "verification_stale", "Source, registry or applicable check attempt changed after the conclusion")
    require(result["evidence_refs"] == evidence_refs(task, stage, directory),
            "verification_stale", "Conclusion must reference the latest exact evidence")
    role = state["roles"].get(result["role_id"])
    require(role and role["kind"] == "verifier" and role["task_id"] == task["plan"]["id"]
            and role["fresh"] is True and role["status"] in {"active", "finished"},
            "role_unavailable", "Conclusion requires its registered independent verifier")
    authors = {state["roles"][ident]["context_id"] for ident in task["roles"]
               if state["roles"][ident]["kind"] == "executor"}
    require(role["context_id"] not in authors, "role_not_independent", "Author cannot supply a conclusion")
    validate_refs(state, task, stage, result["evidence_refs"], directory)
    return result


def require_passed(state, task, directory):
    stage = stage_for(task)
    evidence = valid_evidence(state, task, directory, stage)
    result = applicable(state, task, directory, stage)
    require(result["outcome"] == "passed", "verification_failed", "Every applicable criterion must have a passed conclusion")
    return evidence


def extension(state, task, payload, directory):
    result = applicable(state, task, directory)
    require(payload.get("verification_result") == result["id"] and result["outcome"] in {"failed", "unavailable"},
            "extension_evidence", "Reference the current failed or unavailable verifier conclusion")
    requested = {item["criterion_id"] for item in result["criteria_results"]
                 if item["outcome"] != "passed" and item.get("check_request")}
    additions = payload.get("additional", [])
    require(requested and additions and all(isinstance(check, dict)
            and isinstance(check.get("criteria"), list) and check["criteria"]
            and all(isinstance(value, str) for value in check["criteria"])
            and set(check["criteria"]) <= requested for check in additions),
            "extension_evidence", "Bind each addition to a criterion with a concrete verifier check request")


def transition(state, task, event, directory):
    require(task is not None, "task_required", "Task conclusion required")
    p = event["payload"]
    stage = p.get("stage")
    require(stage in {"independent", "integration"} and stage == stage_for(task),
            "verification_stage", "Use the current independent or integration stage")
    independent(state, task, p.get("role_id"), {"verifier"})
    current(state, task)
    require(p.get("basis") == basis(state, task, "checks", stage),
            "verification_basis", "Use the current source, manifest and complete registry basis")
    refs = evidence_refs(task, stage, directory)
    require(isinstance(p.get("evidence_refs"), list) and p["evidence_refs"] == refs,
            "verification_evidence", "Reference the latest exact check runs, log digests and summaries")
    validate_refs(state, task, stage, refs, directory)
    results = p.get("criteria_results")
    require(isinstance(results, list) and all(isinstance(item, dict) for item in results),
            "verification_criteria", "Provide criterion results")
    identifiers = [item.get("criterion_id") for item in results]
    require(all(isinstance(value, str) for value in identifiers)
            and len(identifiers) == len(set(identifiers)) and set(identifiers) == local_criteria(state, task),
            "verification_criteria", "Cover every applicable criterion exactly once, without foreign criteria")
    for item in results:
        require(item.get("outcome") in {"passed", "failed", "unavailable"}
                and isinstance(item.get("reason"), str) and item["reason"].strip()
                and isinstance(item.get("references"), list) and item["references"]
                and all(isinstance(ref, str) and ref.strip() for ref in item["references"]),
                "verification_criteria", "Each criterion needs an outcome, reason and inspected source/evidence references")
        if "check_request" in item:
            require(item["outcome"] != "passed" and isinstance(item["check_request"], str) and item["check_request"].strip(),
                    "verification_request", "A concrete additional check request belongs to an unconfirmed criterion")
    require(isinstance(p.get("limitations"), list) and all(isinstance(item, str) for item in p["limitations"])
            and p.get("trace"), "verification_schema", "Record limitations and actual verifier trace")
    outcomes = {item["outcome"] for item in results}
    outcome = "failed" if "failed" in outcomes else "unavailable" if "unavailable" in outcomes else "passed"
    if outcome == "passed":
        valid_evidence(state, task, directory, stage)
    result = {**deepcopy(p), "id": event["event_id"], "outcome": outcome,
              "attempts_hash": digest(attempts(task, stage)), "time": now()}
    task.setdefault("verification_results", []).append(result)
    return {"verification_result": result}
