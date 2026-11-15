"""Read-only checks of project requirements; remediation belongs to the dialogue."""
from datetime import datetime, timezone
from pathlib import Path
import platform
import re
import shutil
import subprocess


def check_mise(project, mise_path=None):
    executable = mise_path if mise_path is not None else shutil.which("mise")
    result = {
        "id": "mise", "required": True,
        "title": "mise is installed and runs in the project's working environment",
        "status": "not_found", "executable": executable, "version": None,
        "evidence": {"command": None, "returncode": None, "stdout": "", "stderr": "", "error": None},
    }
    if executable is None:
        result["evidence"]["error"] = "mise was not found on PATH; check the existing installation before installing"
        return result

    path = Path(executable)
    if mise_path is not None and not path.is_absolute():
        raise ValueError("--mise-path must be an absolute path to the mise executable")
    executable = str(path.absolute())
    result["executable"] = executable
    evidence = result["evidence"]
    evidence["command"] = [executable, "--version"]
    result["status"] = "failed"
    if path.suffix.lower() in {".bat", ".cmd"}:
        evidence["error"] = "Use the native mise executable, not a batch wrapper"
        return result
    try:
        run = subprocess.run(
            evidence["command"], cwd=project, shell=False, stdin=subprocess.DEVNULL,
            capture_output=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except FileNotFoundError as exc:
        result["status"] = "not_found"
        evidence["error"] = str(exc)
        return result
    except (OSError, subprocess.TimeoutExpired) as exc:
        evidence["error"] = str(exc)
        return result

    evidence.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
    version = run.stdout.strip().splitlines()[0] if run.stdout.strip() else ""
    if run.returncode != 0:
        evidence["error"] = "mise --version failed; diagnose the reported error before reinstalling"
    elif not re.match(r"^(?:mise )?\d+\.\d+\.\d+(?:[-+][^\s]+)?(?:\s|$)", version):
        evidence["error"] = "mise --version did not return a recognizable version"
    else:
        result.update(status="satisfied", version=version)
    return result


def audit_project(project_root, mise_path=None):
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project-root must be an existing directory")
    requirements = [check_mise(project, mise_path)]
    return {
        "project_root": str(project),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "system": platform.system(), "machine": platform.machine(),
        "requirements": requirements,
        "compliant": all(row["status"] == "satisfied" for row in requirements if row["required"]),
    }
