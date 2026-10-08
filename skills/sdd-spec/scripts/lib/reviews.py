"""Structural review and authorization checks; never proof of user provenance."""
import re
from datetime import datetime
from pathlib import Path

from .documents import InputError, ValidationError, read_document, valid_id
from .paths import contained
from .snapshots import snapshot

STAGES = {"documents": "document_review", "plan": "plan_review"}
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
COMMON = {"schema_version", "change_id", "document_type", "language"}


def require(condition, message):
    if not condition:
        raise ValidationError("review_structure", message)


def fields(value, required, optional=()):
    require(isinstance(value, dict), "Expected a mapping")
    require(set(required) <= value.keys(), f"Missing fields: {sorted(set(required) - value.keys())}")
    require(not value.keys() - set(required) - set(optional), "Unknown fields")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(v) for v in value) and len(value) == len(set(value))


def identity(meta, kind, change_id):
    require(meta.get("document_type", kind) == kind, "Document type disagrees with its role")
    require(meta.get("change_id", change_id) == change_id, "Document change identity mismatch")
    require(text(meta.get("language", "unspecified")), "Language must be text")


def timestamp(value):
    require(text(value), "Timestamp must be quoted text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("timestamp", "Invalid timestamp") from exc
    require(parsed.tzinfo is not None, "Timestamp needs a timezone")
    return parsed


def manifest(value, root, stage):
    require(isinstance(value, list) and value, "Manifest must be a nonempty list")
    names = []
    for entry in value:
        fields(entry, {"path", "sha256"})
        name = entry["path"]
        require(text(name), "Manifest path must be text")
        contained(root, name)
        require("\\" not in name and not any(p in {".", "..", ""} for p in name.split("/")), "Manifest path must be canonical")
        require(name in {"proposal.md", "design.md"} or (stage == "plan_review" and name == "tasks.md") or (name.startswith("specs/") and name.endswith("/spec.md")), "Non-normative manifest input")
        require(isinstance(entry["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "Invalid SHA-256")
        names.append(name)
    require(names == sorted(set(names)), "Manifest paths must be sorted and unique")
    require({"proposal.md", "design.md"} <= set(names) and any(n.startswith("specs/") for n in names), "Incomplete normative manifest")
    require(stage != "plan_review" or "tasks.md" in names, "Plan manifest requires tasks.md")


def required_lenses(project_root: Path) -> list[str]:
    root = contained(Path(project_root), "sdd/arch-lenses")
    index = contained(root, "index.md")
    if not index.exists():
        return ["consistency"]
    doc = read_document(index)
    fields(doc.meta, {"schema_version", "lenses"}, {"document_type", "language"})
    require(doc.meta["schema_version"] == 1, "Unsupported lens index version")
    require(isinstance(doc.meta["lenses"], list), "lenses must be a list")
    result = ["consistency"]
    for lens in doc.meta["lenses"]:
        fields(lens, {"id", "title", "path"})
        require(text(lens["id"]) and SLUG.fullmatch(lens["id"]) and len(lens["id"]) <= 64, "Invalid lens id")
        require(lens["id"] not in result and lens["id"] != "plan", "Duplicate or reserved lens id")
        require(text(lens["title"]) and text(lens["path"]), "Lens title/path required")
        path = contained(root, lens["path"], must_exist=True)
        require(path.is_file(), "Lens path must be a file")
        result.append(lens["id"])
    return result


def _questions(document, root, questions, *, legacy=False):
    for question in document.records:
        fields(question, {"sdd_record", "id", "text", "blocking", "status"}, {"reason", "return_at", "resolution"})
        require(question["sdd_record"] == "question" and valid_id(question["id"], "Q"), "Invalid question record")
        if question["id"] in questions:
            raise ValidationError("duplicate_question", f'Duplicate question ID across discussion files: {question["id"]}', document.path, question["id"])
        require(text(question["text"]) and type(question["blocking"]) is bool and question["status"] in {"open", "resolved"}, "Invalid question fields")
        if question["status"] == "open" and not question["blocking"]:
            require(text(question.get("reason")) and text(question.get("return_at")), "Deferred question needs reason and return_at")
        if not legacy and question["status"] == "resolved":
            require(text(question.get("resolution")), "Resolved question needs a resolution reference")
        if "resolution" in question:
            require(text(question["resolution"]), "Resolution reference must be text")
            require("\0" not in question["resolution"], "Resolution reference must not contain NUL")
            target, separator, fragment = question["resolution"].partition("#")
            require(not separator or text(fragment), "Resolution fragment must be nonempty")
            contained(root, target, must_exist=True)
        questions[question["id"]] = question


def review_status(project_root: Path, change_root: Path, stage: str) -> dict:
    require(stage in STAGES, "Unknown review stage")
    root = Path(change_root)
    project_root = Path(project_root)
    errors, warnings = [], []
    reports, findings, users = {}, {}, {}
    current = {stage: snapshot(project_root, root.name, stage)}

    def diagnose(path, exc, code="review_structure"):
        if isinstance(exc, InputError):
            raise exc
        errors.append({"code": code, "path": str(path), "element_id": None, "message": str(exc)})

    def current_for(review_stage):
        cli_stage = "plan" if review_stage == "plan_review" else "documents"
        if cli_stage not in current:
            try:
                current[cli_stage] = snapshot(project_root, root.name, cli_stage)
            except InputError:
                if cli_stage == stage:
                    raise
                # Historical evidence for another stage can outlive its inputs.
                # An unavailable manifest never matches an approval or report.
                current[cli_stage] = None
        return current[cli_stage]

    try:
        lenses = required_lenses(project_root)
    except (ValidationError, TypeError, KeyError) as exc:
        diagnose(project_root / "sdd/arch-lenses/index.md", exc, "lens_index")
        lenses = ["consistency"]
    required = lenses if stage == "documents" else ["plan"]
    review_root = contained(root, "review")
    for path in sorted(review_root.glob("*/*.md")):
        try:
            contained(root, path.relative_to(root).as_posix(), must_exist=True)
            doc = read_document(path)
            meta = doc.meta
            identity(meta, "review", root.name)
            fields(meta, {"schema_version", "run_id", "stage", "lens_id", "result", "started_at", "finished_at", "inputs", "inputs_after", "freshness", "limitations"}, COMMON)
            require(meta["stage"] in STAGES.values(), "Invalid report stage")
            require(meta.get("change_id", root.name) == root.name, "Report change mismatch")
            require(meta["run_id"] == path.parent.name and meta["lens_id"] == path.stem, "Report identity disagrees with path")
            require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", meta["run_id"]), "Invalid run id")
            require(SLUG.fullmatch(meta["lens_id"]) is not None, "Invalid lens id")
            require((meta["lens_id"] == "plan") == (meta["stage"] == "plan_review"), "Lens/stage mismatch")
            require(meta["result"] in {"completed_no_findings", "completed_with_findings", "incomplete"}, "Invalid report result")
            require(meta["freshness"] in {"current", "stale"}, "Invalid recorded freshness")
            require(timestamp(meta["finished_at"]) >= timestamp(meta["started_at"]), "Report ends before start")
            require(strings(meta["limitations"]), "limitations must be a text list")
            manifest(meta["inputs"], root, meta["stage"])
            manifest(meta["inputs_after"], root, meta["stage"])
            local = {}
            for record in doc.records:
                fields(record, {"sdd_record", "id", "source", "target", "severity", "problem", "impact", "suggestion"})
                require(record["sdd_record"] == "finding", "Reports only contain findings")
                require(valid_id(record["id"], "FIND"), "Invalid finding id")
                require(record["id"] not in local, "Duplicate finding id")
                require(record["severity"] in {"blocker", "recommendation"}, "Invalid finding severity")
                require(all(text(record[k]) for k in ("source", "problem", "impact", "suggestion")), "Finding text required")
                fields(record["target"], {"path"}, {"element_id"})
                contained(root, record["target"]["path"])
                require("element_id" not in record["target"] or text(record["target"]["element_id"]), "Target element_id must be text")
                local[record["id"]] = record
            require(meta["result"] != "completed_no_findings" or not local, "No-findings report has findings")
            require(meta["result"] != "completed_with_findings" or bool(local), "With-findings report has no findings")
            key = f'{meta["run_id"]}/{meta["lens_id"]}'
            freshness = "current" if meta["inputs"] == meta["inputs_after"] == current_for(meta["stage"]) else "stale"
            reports[key] = {"stage": meta["stage"], "lens_id": meta["lens_id"], "result": meta["result"], "freshness": freshness, "inputs": meta["inputs"]}
            findings.update({f"{key}/{ident}": record for ident, record in local.items()})
        except (ValidationError, TypeError, KeyError) as exc:
            diagnose(path, exc)

    # Every lens in a run must have reviewed one common input set.
    run_inputs = {}
    for key, report in reports.items():
        run = (key.split("/")[0], report["stage"])
        if run in run_inputs and run_inputs[run] != report["inputs"]:
            diagnose(review_root / key, ValidationError("authorization_structure", "Run used different input manifests"))
            for other_key, other in reports.items():
                if (other_key.split("/")[0], other["stage"]) == run:
                    other["freshness"] = "stale"
        run_inputs[run] = report["inputs"]

    summary = contained(root, "review/summary.md")
    if summary.exists():
        try:
            doc = read_document(summary)
            identity(doc.meta, "summary", root.name)
            fields(doc.meta, {"schema_version", "findings"}, COMMON)
            require(isinstance(doc.meta["findings"], list), "Summary findings must be a list")
            for entry in doc.meta["findings"]:
                fields(entry, {"finding", "related_to", "duplicates"})
                require(strings(entry["related_to"]) and strings(entry["duplicates"]), "Summary links must be lists")
                require(all(k in findings for k in [entry["finding"], *entry["related_to"], *entry["duplicates"]]), "Unknown full finding key")
        except (ValidationError, TypeError, KeyError) as exc:
            diagnose(summary, exc)

    decisions = contained(root, "review/decisions.md")
    if decisions.exists():
        try:
            doc = read_document(decisions)
            identity(doc.meta, "decisions", root.name)
            fields(doc.meta, {"schema_version"}, COMMON)
            for record in doc.records:
                try:
                    _validate_user(record, root, findings)
                    require(record["kind"] != "finding_disposition" or all(reports["/".join(key.split("/")[:2])]["stage"] == record["scope"]["stage"] for key in record["scope"].get("findings", [])), "Disposition stage mismatch")
                    require(record["id"] not in users, "Duplicate USER id")
                    users[record["id"]] = record
                except (ValidationError, TypeError, KeyError) as exc:
                    diagnose(decisions, exc, "authorization_structure")
        except (ValidationError, TypeError, KeyError) as exc:
            diagnose(decisions, exc, "authorization_structure")

    superseded = set()
    for ident, record in users.items():
        for old in record.get("supersedes", []):
            if old not in users or old == ident:
                diagnose(decisions, ValidationError("authorization_structure", "Invalid superseded USER reference"), "authorization_structure")
            elif timestamp(users[old]["date"]) >= timestamp(record["date"]):
                diagnose(decisions, ValidationError("authorization_structure", "Superseding decision must be later"), "authorization_structure")
            else:
                superseded.add(old)
    active = {i: r for i, r in users.items() if i not in superseded and r.get("status", "active") != "cancelled"}
    applicable = {}
    for ident, record in active.items():
        kind = record["kind"]
        applicable[ident] = kind not in {"document_approval", "plan_approval", "review_waiver"} or record["inputs"] == current_for(record["scope"]["stage"])

    dispositions = {}
    for ident, record in active.items():
        if record["kind"] == "finding_disposition":
            for key in record["scope"]["findings"]:
                if key in dispositions:
                    diagnose(decisions, ValidationError("authorization_structure", "Conflicting active dispositions require supersedes"), "authorization_structure")
                dispositions[key] = record
    unresolved, unfinished = [], []
    for key in findings:
        if reports["/".join(key.split("/")[:2])]["stage"] != STAGES[stage]:
            continue
        decision = dispositions.get(key)
        if decision is None:
            unresolved.append(key)
        elif decision["action"] == "fix" and key not in {c["finding"] for c in decision.get("completion", [])}:
            unfinished.append(key)

    coverage = {}
    for lens in required:
        matches = [r for r in reports.values() if r["stage"] == STAGES[stage] and r["lens_id"] == lens]
        waived = any(applicable[i] and r["kind"] == "review_waiver" and r["scope"]["stage"] == STAGES[stage] and lens in r["scope"]["lenses"] for i, r in active.items())
        coverage[lens] = "completed" if any(r["freshness"] == "current" and r["result"] != "incomplete" for r in matches) else "waived" if waived else "incomplete" if any(r["freshness"] == "current" for r in matches) else "stale" if matches else "missing"
    approved_kind = "document_approval" if stage == "documents" else "plan_approval"
    approved = any(applicable[i] and r["kind"] == approved_kind for i, r in active.items())
    complete = all(v in {"completed", "waived"} for v in coverage.values())
    work = {i: r["scope"] for i, r in active.items() if r["kind"] in {"planning_command", "finding_disposition"} and r.get("status", "active") == "active" and (r["kind"] == "planning_command" or r["action"] == "fix")}
    for ident in list(work):
        record = active[ident]
        if record["kind"] == "finding_disposition":
            completed = {c["finding"] for c in record.get("completion", [])}
            remaining = [key for key in record["scope"]["findings"] if key not in completed]
            if remaining:
                work[ident] = {**record["scope"], "findings": remaining}
            else:
                del work[ident]
    questions, discussion_valid = {}, True
    questions_path = root / "questions.md"
    try:
        questions_path = contained(root, "questions.md")
        if questions_path.exists():
            discussion = read_document(questions_path)
            fields(discussion.meta, COMMON)
            identity(discussion.meta, "questions", root.name)
            _questions(discussion, root, questions)
    except (ValidationError, TypeError, KeyError, OSError) as exc:
        discussion_valid = False
        errors.append({"code": "questions_structure", "path": str(questions_path), "element_id": getattr(exc, "element_id", None), "message": str(exc)})
    state = root / "state.md"
    try:
        state = contained(root, "state.md")
        if state.exists():
            checkpoint = read_document(state)
            _questions(checkpoint, root, questions, legacy=True)
            identity(checkpoint.meta, "state", root.name)
            fields(checkpoint.meta, {"schema_version", "change_id", "phase", "awaiting", "updated_at", "document_links", "review_links", "approval_refs"}, {"document_type", "language"})
            require(checkpoint.meta["change_id"] == root.name, "State change mismatch")
            require(checkpoint.meta["phase"] in {"discovery", "drafting", "document_review", "user_review", "planning", "plan_review", "plan_approved"}, "Invalid state phase")
            require(checkpoint.meta["awaiting"] in {"none", "clarification", "review_consent", "planning_command", "final_approval"}, "Invalid awaiting value")
            timestamp(checkpoint.meta["updated_at"])
            for field in ("document_links", "review_links"):
                require(strings(checkpoint.meta[field]), "State links must be unique text lists")
                for link in checkpoint.meta[field]:
                    contained(root, link, must_exist=True)
            require(strings(checkpoint.meta.get("approval_refs", [])), "approval_refs must be a list")
            require(all(i in users for i in checkpoint.meta.get("approval_refs", [])), "State refers to missing USER decision")
        else:
            # Legacy bundles may have valid approval evidence without a checkpoint.
            warnings.append({"code": "state_recovery", "path": str(state), "element_id": None, "message": "State is missing; recover a draft checkpoint without inferring approvals."})
    except (ValidationError, TypeError, KeyError, OSError) as exc:
        discussion_valid = False
        duplicate = getattr(exc, "code", None) == "duplicate_question"
        (errors if duplicate else warnings).append({"code": "duplicate_question" if duplicate else "state_recovery", "path": str(state), "element_id": getattr(exc, "element_id", None), "message": str(exc)})
    open_questions = sorted(i for i, question in questions.items() if question["status"] == "open")
    blocking_questions = [i for i in open_questions if questions[i]["blocking"]]
    discussion_status = {"open_questions": open_questions, "blocking_questions": blocking_questions, "complete": discussion_valid and not blocking_questions, "provenance": "Structural checks of available question records only; decision journal authorship and semantic completeness are not verified."}
    return {"errors": errors, "warnings": warnings, "discussion_status": discussion_status, "review_status": {"required_lenses": required, "coverage": coverage, "reports": reports, "complete": complete, "unresolved_findings": unresolved, "unfinished_fixes": unfinished}, "approval_status": {"approved": approved, "ready": approved and complete and discussion_status["complete"] and not unresolved and not unfinished and not errors, "applicability": applicable, "work_authorizations": work, "provenance": "Recorded decisions; user authorship and change provenance are not verified."}}


def _validate_user(record, root, findings):
    fields(record, {"sdd_record", "id", "kind", "scope", "response", "date", "inputs"}, {"message", "status", "supersedes", "action", "reason", "return_at", "completion"})
    require(record["sdd_record"] == "user", "Expected USER record")
    require(valid_id(record["id"], "USER"), "Invalid USER id")
    kinds = {"review_consent", "finding_disposition", "review_waiver", "document_approval", "planning_command", "plan_approval"}
    require(record["kind"] in kinds, "Invalid authorization kind")
    require(text(record["response"]), "Explicit response required")
    require("message" not in record or text(record["message"]), "Message reference must be text")
    timestamp(record["date"])
    require(record.get("status", "active") in {"active", "completed", "cancelled"}, "Invalid authorization status")
    require(strings(record.get("supersedes", [])), "supersedes must be a unique list")
    scope, kind = record["scope"], record["kind"]
    expected = {"review_consent": {"run_id", "lenses"}, "review_waiver": {"lenses"}, "finding_disposition": {"findings"}, "planning_command": {"work"}}.get(kind, set())
    fields(scope, {"stage"} | expected)
    require(scope["stage"] in STAGES.values(), "Invalid authorization stage")
    if kind in {"document_approval", "planning_command"}:
        require(scope["stage"] == "document_review", "Document authorization requires document_review")
    if kind == "plan_approval":
        require(scope["stage"] == "plan_review", "Plan approval requires plan_review")
    manifest(record["inputs"], root, scope["stage"])
    if "lenses" in scope:
        require(strings(scope["lenses"]) and scope["lenses"], "Explicit lenses required")
        require(all(SLUG.fullmatch(lens) for lens in scope["lenses"]), "Invalid lens id")
        require((scope["lenses"] == ["plan"]) if scope["stage"] == "plan_review" else "plan" not in scope["lenses"], "Authorization lens/stage mismatch")
    if "run_id" in scope:
        require(text(scope["run_id"]) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", scope["run_id"]), "Explicit run required")
    if "work" in scope:
        require(text(scope["work"]), "Bounded work description required")
    if kind == "finding_disposition":
        require(strings(scope["findings"]) and scope["findings"], "Explicit findings required")
        require(all(k in findings for k in scope["findings"]), "Unknown full finding key")
        require(record.get("action") in {"fix", "reject", "defer"}, "Invalid disposition")
        if record["action"] in {"reject", "defer"}:
            require(text(record.get("reason")), "Disposition reason required")
        if record["action"] == "defer":
            require(text(record.get("return_at")), "Deferred finding needs return_at")
        require(isinstance(record.get("completion", []), list), "completion must be a list")
        completed = set()
        for completion in record.get("completion", []):
            fields(completion, {"finding", "path"})
            require(record["action"] == "fix" and completion["finding"] in scope["findings"] and completion["finding"] not in completed, "Completion outside unique fix scope")
            contained(root, completion["path"], must_exist=True)
            completed.add(completion["finding"])
    else:
        require(not set(record) & {"action", "reason", "return_at", "completion"}, "Disposition fields on unrelated authorization")
