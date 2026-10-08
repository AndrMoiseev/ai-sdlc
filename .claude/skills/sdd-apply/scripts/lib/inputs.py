"""Use sdd-spec's validator and parser rather than a second SDD dialect."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from .common import contained, digest, git, require


def companion(project, explicit=None):
    candidates = [Path(explicit)] if explicit else [Path(__file__).resolve().parents[3] / "sdd-spec", Path(project) / ".agents/skills/sdd-spec", Path(project) / ".claude/skills/sdd-spec", Path.home() / ".agents/skills/sdd-spec", Path.home() / ".claude/skills/sdd-spec"]
    for root in candidates:
        if all((root / p).is_file() for p in ("SKILL.md", "scripts/check.py", "scripts/check.py.lock", "scripts/snapshot.py", "scripts/snapshot.py.lock", "scripts/lib/documents.py")):
            return root.resolve()
    raise ValueError("sdd-spec unavailable or incompatible: install its complete package")


def spec_modules(root):
    name = "_sdd_spec_" + digest(str(root))[:12]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / "scripts/lib/__init__.py", submodule_search_locations=[str(root / "scripts/lib")])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return __import__(name + ".documents", fromlist=["read_document"])


def spec_call(dependency, project, change, stage, script):
    result = subprocess.run(["uv", "run", "--locked", "--script", str(dependency / "scripts" / script), "--project-root", str(project), "--change", change, "--stage", stage], capture_output=True)
    require(result.returncode == 0, "sdd_check", result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace"))
    return json.loads(result.stdout)


def validate(project_root, change=None, instruction=None, sdd_spec=None):
    project = Path(project_root).resolve(strict=True)
    require(bool(instruction and instruction.get("text") and instruction.get("source")), "execution_instruction", "Record the user's execution instruction and message source")
    if change is None:
        candidates = sorted(p.name for p in (project / "sdd/changes").iterdir() if (p / "tasks.md").exists())
        require(len(candidates) == 1, "ambiguous_change", f"Select change: {candidates}")
        change = candidates[0]
    require(isinstance(change, str) and "/" not in change and "\\" not in change and change not in {".", ".."}, "change_id", "Invalid change ID")
    directory = contained(project, "sdd/changes/" + change)
    require((directory / "tasks.md").is_file(), "missing_plan", "Return to sdd-spec for an approved plan")
    dependency = companion(project, sdd_spec)
    checks = {}
    for stage in ("documents", "plan"):
        checks[stage] = spec_call(dependency, project, change, stage, "check.py")
        require(checks[stage].get("schema_version") == 1 and checks[stage].get("approval_status", {}).get("ready") is True, "approval_missing", f"{stage}: {checks[stage]}")
        require(not any(w["code"] == "state_recovery" for w in checks[stage].get("warnings", [])), "state_recovery", "Recover sdd-spec checkpoint first")
    docs = spec_modules(dependency)
    checkpoint = docs.read_document(directory / "state.md")
    require(not any(r.get("blocking") and r.get("status") == "open" for r in checkpoint.records), "open_question", "Resolve blocking questions in sdd-spec")
    tasks = docs.read_document(directory / "tasks.md").records
    manifest = spec_call(dependency, project, change, "plan", "snapshot.py")
    head = git(project, "rev-parse", "HEAD")
    require(not git(project, "ls-files", "--unmerged"), "unmerged_index", "Resolve the existing Git conflict before execution")
    branch = git(project, "symbolic-ref", "--quiet", "--short", "HEAD")
    git(project, "var", "GIT_AUTHOR_IDENT")
    git(project, "var", "GIT_COMMITTER_IDENT")
    index = git(project, "diff", "--cached", "--binary", raw=True)
    dirty = set()
    for args in (("diff", "--name-only", "--cached", "-z"), ("diff", "--name-only", "-z"), ("ls-files", "--others", "--exclude-standard", "-z")):
        dirty.update(filter(None, git(project, *args, raw=True).decode("utf-8").split("\0")))
    return {"schema_version": 1, "project_root": str(project), "change_id": change, "change_root": str(directory), "instruction": instruction, "sdd_spec": str(dependency), "checks": checks, "manifest": manifest, "tasks": tasks, "head": head, "branch": branch, "dirty_paths": sorted(dirty), "index_patch": index.decode("utf-8", "replace"), "status": git(project, "status", "--porcelain=v1", "-z", raw=True).decode("utf-8"), "working_patch": git(project, "diff", "--binary", raw=True).decode("utf-8", "replace")}
