"""Read approved documents through the versioned sdd-shared API."""
from .repository import repository
from shared import locate, load
import json
from pathlib import Path
import subprocess
import sys
from .common import require


def spec_modules(module_name="documents"):
    return load(module_name)


def document_paths(basis):
    """List plan documents from the main working branch, without saved inventory."""
    paths = ["proposal.md", "design.md", "tasks.md"]
    if basis.get("work_kind", "change") == "change":
        relative = Path(basis["change_root"]).relative_to(Path(basis["project_root"]))
        prefix = relative.as_posix() + "/"
        paths.extend(name[len(prefix):] for name in repository(basis["project_root"]).tracked("HEAD")
                     if name.startswith(prefix + "specs/") and name.endswith("/spec.md"))
    return sorted(paths)


def read_plan_document(basis, name):
    """Extract document records from HEAD of the original project repository."""
    from .common import contained
    require(name in document_paths(basis), "basis_paths", "Document is outside the plan at project HEAD")
    docs = spec_modules()
    path = contained(basis["change_root"], name).relative_to(Path(basis["project_root"]))
    text = repository(basis["project_root"]).content("HEAD", path.as_posix()).decode("utf-8-sig")
    require(text.strip(), "basis_document_missing", f"Plan document unavailable at project HEAD: {name}")
    records = []
    for token in docs.parse_markdown(text):
        if token.type != "fence" or token.info.strip() != "yaml":
            continue
        try:
            record = docs.safe_yaml(token.content)
        except docs.ValidationError as exc:
            if exc.code == "yaml_mapping":
                continue
            raise
        if "sdd_record" in record:
            records.append(record)
    return records


def spec_call(dependency, project, change, stage, script, work_kind="change"):
    command = ["uv", "run", "--locked", "--script", str(dependency / "scripts" / script), "--project-root", str(project), "--change", change, "--stage", stage]
    if work_kind != "change":
        command += ["--work-kind", work_kind]
    result = subprocess.run(command, capture_output=True, shell=False)
    require(result.returncode == 0, "sdd_check", result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace"))
    return json.loads(result.stdout)


def validate(project_root, change=None, instruction=None, work_kind="change"):
    project = Path(project_root).resolve(strict=True)
    require(bool(instruction and instruction.get("text") and instruction.get("source")), "execution_instruction", "Record the user's plan approval or execution instruction and its source")
    require(work_kind is None or work_kind in ("change", "refactoring"), "work_kind", "Expected change, refactoring or null for discovery")
    dependency = locate(work_kind=work_kind or "change")
    paths = spec_modules("paths")
    if work_kind is None or change is None:
        candidates = [entry for entry in paths.list_work(project, change)
                      if work_kind is None or entry["work_kind"] == work_kind]
        if work_kind is not None and change is None:
            candidates = [entry for entry in candidates if entry["has_plan"]]
        require(len(candidates) == 1, "ambiguous_change", f"Select work by work_kind and change_id: {candidates}")
        work_kind, change = candidates[0]["work_kind"], candidates[0]["change_id"]
        dependency = locate(work_kind=work_kind)
    directory = paths.change_root(project, change, work_kind)
    require((directory / "tasks.md").is_file(), "missing_plan", "Return to sdd-spec for an approved plan")
    checks = {}
    for stage in ("documents", "plan"):
        checks[stage] = spec_call(dependency, project, change, stage, "check.py", work_kind)
        require(checks[stage].get("schema_version") == 2 and checks[stage].get("approval_status", {}).get("ready") is True, "approval_missing", f"{stage}: {checks[stage]}")
        require(checks[stage].get("checkpoint_status", {}).get("status") == "ready", "checkpoint_not_ready", f"{stage}: accept a clean checkpoint before execution: {checks[stage].get('checkpoint_status')}")
        require(not any(w["code"] == "state_recovery" for w in checks[stage].get("warnings", [])), "state_recovery", "Recover sdd-spec checkpoint first")
    docs = spec_modules()
    docs.read_checkpoint(directory, work_kind)
    records = docs.read_document(directory / "tasks.md", work_kind).records
    tasks = [record for record in records if record["sdd_record"] == "task"]
    plan_records = {}
    if work_kind == "refactoring":
        plan_records = {kind: [record for record in records if record["sdd_record"] == kind]
                        for kind in ("acceptance", "verification")}
    excluded = (directory / "execution").relative_to(project).as_posix()
    source = repository(project).inspect(exclude=[excluded])
    require(source["head"] == checks["plan"]["checkpoint_status"]["head"] and not source["dirty_paths"], "checkpoint_changed", "Checkpoint changed during admission; inspect and retry")
    return {"schema_version": 2, "project_root": str(project), "work_kind": work_kind, "change_id": change, "change_root": str(directory), "instruction": instruction, "tasks": tasks, **plan_records, "head": source["head"], "branch": source["branch"]}
