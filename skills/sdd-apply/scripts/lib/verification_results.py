"""Independent criterion conclusions tied to exact current execution evidence."""
from copy import deepcopy
import json

from . import artifact_storage as artifacts
from .common import digest, now, require
from .explorer_assignments import basis
from .verification import current, independent, local_criteria, valid_evidence


def stage_for(task):
    return "integration" if task.get("worktree") and task["worktree"].get("integrated") else "independent"


def scope(state, task):
    if task is not None:
        return task
    from .final_checks import registry
    return registry(state)


def criteria(state, task):
    if task is not None:
        return local_criteria(state, task)
    from .final_checks import required_criteria
    return required_criteria(state)


def ready(state, task, stage):
    if stage == "final":
        from .final_checks import ready as final_ready
        final_ready(state)
    if task is not None:
        current(state, task)


def verifier(state, task, role_id, stage, active=True):
    if stage != "final" and active:
        return independent(state, task, role_id, {"verifier"})
    role = state["roles"].get(role_id)
    require(role and role["kind"] == ("final_verifier" if stage == "final" else "verifier")
            and role["task_id"] == (task["plan"]["id"] if task else None)
            and role["status"] in ({"active"} if active else {"active", "finished"}),
            "role_unavailable", "Conclusion requires its registered independent verifier")
    authors = {value["context_id"] for value in state["roles"].values()
               if value["kind"] == "executor" and (stage == "final" or value["task_id"] == task["plan"]["id"])}
    require(role["fresh"] is True and role["context_id"] not in authors,
            "role_not_independent", "Author cannot supply a conclusion")
    if stage == "final":
        require(not any(other["context_id"] == role["context_id"]
                        for ident, other in state["roles"].items() if ident != role_id),
                "final_role", "Final conclusion requires a fresh separate final verifier")
    return role


def attempts(task, stage):
    # Include procedure attempts and pending procedures: a newer unfinished or
    # failed procedure must invalidate a conclusion about its previous aggregate.
    return {"evidence": [item for item in task["evidence"] if item.get("stage", "final") == stage],
            "procedures": {key: value for key, value in task.get("procedures", {}).items()
                           if value.get("stage", "final") == stage}}


def evidence_refs(task, stage, directory):
    latest = {}
    for item in task["evidence"]:
        if item.get("stage", "final") == stage and not item.get("procedure"):
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


def packet(state, task, directory, stage=None):
    stage = stage or stage_for(task)
    return {"stage": stage, "basis": basis(state, task, "checks", stage),
            "criteria": sorted(criteria(state, task)),
            "evidence_refs": evidence_refs(scope(state, task), stage, directory)}


def validate_refs(state, task, stage, refs, directory):
    from .check_evidence import validate
    from .check_registry import selected
    if task is None:
        from .final_checks import applicable as final_checks
        checks = final_checks(state)
    else:
        checks = selected(state, task, final=stage == "final")
    expected = basis(state, task, "checks", stage)
    source = expected["source"]
    validated = set()
    for ref in refs:
        if ref["log"] in validated:
            continue
        record = json.loads(artifacts.read_bytes(artifacts.contained(directory, ref["log"])))
        identity = record.get("basis", {}) if task is None else record
        require(identity.get("run_id") == state["run_id"]
                and record.get("task_id") == (task["plan"]["id"] if task else None)
                and record.get("stage") == stage
                and (record.get("basis") == expected if task is None else record.get("before") == source)
                and record.get("after") == source,
                "verification_basis", "Conclusion evidence must belong to this task, stage and unchanged source")
        from .explorer_assignments import authorize
        role = authorize(state, task, record.get("role_id"), stage, active=False)
        authors = {value["context_id"] for value in state["roles"].values()
                   if value["kind"] == "executor" and (stage == "final" or value["task_id"] == task["plan"]["id"])}
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
    holder = scope(state, task)
    results = holder.get("verification_results", [])
    result = next((item for item in reversed(results) if item["stage"] == stage), None)
    require(result is not None, "verification_missing", "A current verifier conclusion is required")
    ready(state, task, stage)
    require(result["basis"] == basis(state, task, "checks", stage)
            and result["attempts_hash"] == digest(attempts(holder, stage)),
            "verification_stale", "Source, registry or applicable check attempt changed after the conclusion")
    require(result["evidence_refs"] == evidence_refs(holder, stage, directory),
            "verification_stale", "Conclusion must reference the latest exact evidence")
    verifier(state, task, result["role_id"], stage, active=False)
    validate_refs(state, task, stage, result["evidence_refs"], directory)
    return result


def execution(state, task, directory, stage):
    if task is not None:
        return valid_evidence(state, task, directory, stage)
    from .final_checks import evidence as final_evidence
    _, evidence, gaps = final_evidence(state, directory)
    require(not gaps, "required_checks", "Every required final command/procedure must pass: " + str(gaps))
    require(criteria(state, task) <= {criterion for item in evidence for criterion in item["criteria"]},
            "criteria_uncovered", "Final evidence must cover every applicable criterion")
    return evidence


def require_passed(state, task, directory, stage=None):
    stage = stage or stage_for(task)
    evidence = execution(state, task, directory, stage)
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
    p = event["payload"]
    stage = p.get("stage")
    require(stage == "final" or task is not None and stage in {"independent", "integration"} and stage == stage_for(task),
            "verification_stage", "Use the current independent/integration stage or final")
    require(not (stage == "final" and task is not None and state["basis"].get("work_kind") == "refactoring"),
            "final_role", "Refactoring final conclusion uses the whole null scope")
    verifier(state, task, p.get("role_id"), stage)
    ready(state, task, stage)
    holder = scope(state, task)
    require(p.get("basis") == basis(state, task, "checks", stage),
            "verification_basis", "Use the current source, manifest and complete registry basis")
    refs = evidence_refs(holder, stage, directory)
    require(isinstance(p.get("evidence_refs"), list) and p["evidence_refs"] == refs,
            "verification_evidence", "Reference the latest exact check runs, log digests and summaries")
    validate_refs(state, task, stage, refs, directory)
    results = p.get("criteria_results")
    require(isinstance(results, list) and all(isinstance(item, dict) for item in results),
            "verification_criteria", "Provide criterion results")
    identifiers = [item.get("criterion_id") for item in results]
    require(all(isinstance(value, str) for value in identifiers)
            and len(identifiers) == len(set(identifiers)) and set(identifiers) == criteria(state, task),
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
        execution(state, task, directory, stage)
    result = {**deepcopy(p), "id": event["event_id"], "outcome": outcome,
              "attempts_hash": digest(attempts(holder, stage)), "time": now()}
    holder.setdefault("verification_results", []).append(result)
    if stage == "final":
        state["final"] = None
    return {"verification_result": result}
