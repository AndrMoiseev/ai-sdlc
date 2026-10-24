"""Read approved documents through the versioned sdd-shared API."""
from shared import locate, load
import json
from pathlib import Path
import subprocess
import sys
from .common import git, require


def companion(project, explicit=None, sdd_shared=None, work_kind="change"):
    """Legacy explicit is an sdd-spec root; shared is the runtime dependency."""
    return locate(explicit=sdd_shared, legacy=explicit, work_kind=work_kind)


def spec_modules(root, module_name="documents"):
    """Compatibility helper for callers passing an old sdd-spec root."""
    root = Path(root)
    return load(root if (root / "api.json").is_file() else locate(legacy=root), module_name)


def basis_dependency(basis):
    return locate(explicit=basis.get("sdd_shared"),
                  legacy=basis.get("sdd_spec") if not basis.get("sdd_shared") else None)


def spec_call(dependency, project, change, stage, script, work_kind="change"):
    command = ["uv", "run", "--locked", "--script", str(dependency / "scripts" / script), "--project-root", str(project), "--change", change, "--stage", stage]
    if work_kind != "change":
        command += ["--work-kind", work_kind]
    result = subprocess.run(command, capture_output=True, shell=False)
    require(result.returncode == 0, "sdd_check", result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace"))
    return json.loads(result.stdout)


def validate(project_root, change=None, instruction=None, sdd_spec=None, sdd_shared=None, work_kind="change"):
    project = Path(project_root).resolve(strict=True)
    require(bool(instruction and instruction.get("text") and instruction.get("source")), "execution_instruction", "Record the user's execution instruction and message source")
    require(work_kind is None or work_kind in ("change", "refactoring"), "work_kind", "Expected change, refactoring or null for discovery")
    dependency = companion(project, sdd_spec, sdd_shared, work_kind or "change")
    paths = spec_modules(dependency, "paths")
    if work_kind is None or change is None:
        candidates = [entry for entry in paths.list_work(project, change)
                      if work_kind is None or entry["work_kind"] == work_kind]
        if work_kind is not None and change is None:
            candidates = [entry for entry in candidates if entry["has_plan"]]
        require(len(candidates) == 1, "ambiguous_change", f"Select work by work_kind and change_id: {candidates}")
        work_kind, change = candidates[0]["work_kind"], candidates[0]["change_id"]
        dependency = companion(project, sdd_spec, sdd_shared, work_kind)
    directory = paths.change_root(project, change, work_kind)
    require((directory / "tasks.md").is_file(), "missing_plan", "Return to sdd-spec for an approved plan")
    checks = {}
    for stage in ("documents", "plan"):
        checks[stage] = spec_call(dependency, project, change, stage, "check.py", work_kind)
        require(checks[stage].get("schema_version") == 1 and checks[stage].get("approval_status", {}).get("ready") is True, "approval_missing", f"{stage}: {checks[stage]}")
        require(not any(w["code"] == "state_recovery" for w in checks[stage].get("warnings", [])), "state_recovery", "Recover sdd-spec checkpoint first")
    docs = spec_modules(dependency)
    checkpoint = docs.read_document(directory / "state.md", work_kind)
    require(not any(r.get("blocking") and r.get("status") == "open" for r in checkpoint.records), "open_question", "Resolve blocking questions in sdd-spec")
    records = docs.read_document(directory / "tasks.md", work_kind).records
    tasks = [record for record in records if record["sdd_record"] == "task"]
    plan_records = {}
    if work_kind == "refactoring":
        plan_records = {kind: [record for record in records if record["sdd_record"] == kind]
                        for kind in ("acceptance", "verification")}
    manifest = spec_call(dependency, project, change, "plan", "snapshot.py", work_kind)
    head = git(project, "rev-parse", "HEAD")
    require(not git(project, "ls-files", "--unmerged"), "unmerged_index", "Resolve the existing Git conflict before execution")
    branch = git(project, "symbolic-ref", "--quiet", "--short", "HEAD")
    git(project, "var", "GIT_AUTHOR_IDENT")
    git(project, "var", "GIT_COMMITTER_IDENT")
    index = git(project, "diff", "--cached", "--binary", raw=True)
    dirty = set()
    for args in (("diff", "--name-only", "--cached", "-z"), ("diff", "--name-only", "-z"), ("ls-files", "--others", "--exclude-standard", "-z")):
        dirty.update(filter(None, git(project, *args, raw=True).decode("utf-8").split("\0")))
    return {"schema_version": 1, "project_root": str(project), "work_kind": work_kind, "change_id": change, "change_root": str(directory), "instruction": instruction, "sdd_shared": str(dependency), "checks": checks, "manifest": manifest, "tasks": tasks, **plan_records, "head": head, "branch": branch, "dirty_paths": sorted(dirty), "index_patch": index.decode("utf-8", "replace"), "status": git(project, "status", "--porcelain=v1", "-z", raw=True).decode("utf-8"), "working_patch": git(project, "diff", "--binary", raw=True).decode("utf-8", "replace")}
