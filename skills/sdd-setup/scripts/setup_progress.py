"""Record verified setup steps in project settings. Applicability belongs to the caller."""
from contextlib import nullcontext
import json
from pathlib import Path

from setup_core import read_json, replace_file, require, safe_target, setup_lock


STEPS = ("mise", "common-tools", "jdk", "gradle", "junit5", "jacoco", "archunit",
         "ktlint", "detekt", "typespec", "collection", "mise-tasks", "roles")


def progress(project_root, applicable=None, complete=None, reset=None, project_changed=False, failed=None,
             check_exit_codes=()):
    project = Path(project_root).resolve(strict=True)
    require(project.is_dir(), "Expected a project directory")
    require(not project_changed or complete, "--project-changed requires a successfully completed step")
    require(sum(bool(value) for value in (complete, reset, failed)) <= 1, "Choose a single progress operation")
    selected = STEPS if applicable is None else applicable
    require(set(selected) <= set(STEPS), "Unknown applicable step")
    if complete:
        require(complete in selected, "Cannot complete a step outside the applicable scope")
    if complete in ("ktlint", "detekt"):
        require(check_exit_codes, f"Provide --check-exit-code for each project {complete} check")
        if any(code != 0 for code in check_exit_codes):
            failed, complete = complete, None
    elif check_exit_codes:
        raise ValueError("--check-exit-code belongs to completion of ktlint or detekt")
    if failed:
        require(failed in selected, "Failed step outside the applicable scope")
    if reset:
        require(reset == ["all"] or set(reset) <= set(STEPS), "Use 'all' alone or name known steps")

    lock = setup_lock(project, "progress") if complete or reset else nullcontext()
    with lock:
        path = safe_target(project, ".sdd/settings.json")
        settings = read_json(path) if path.exists() else {"schema_version": 1}
        require(isinstance(settings, dict) and type(settings.get("schema_version")) is int
                and settings["schema_version"] == 1, "Expected settings schema_version 1")
        setup = settings.get("setup", {})
        require(isinstance(setup, dict), "Expected settings.setup to be an object")
        recorded = setup.get("completed_steps", [])
        require(isinstance(recorded, list) and all(isinstance(step, str) and step for step in recorded)
                and len(set(recorded)) == len(recorded), "Expected distinct step names in setup.completed_steps")
        completed = recorded.copy()
        if reset:
            completed = [] if reset == ["all"] else [step for step in recorded if step not in reset]
        if complete and complete not in completed:
            completed.append(complete)
        if completed != recorded:
            settings.setdefault("setup", {})["completed_steps"] = completed
            replace_file(path, (json.dumps(settings, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    pending = [step for step in STEPS if step in selected and step not in completed]
    return {"completed_steps": completed, "pending_steps": pending, "next_step": next(iter(pending), None),
            "failed_step": failed, "stop": bool(failed or project_changed or not pending)}
