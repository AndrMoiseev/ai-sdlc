"""Read-only checks of project requirements; remediation belongs to the dialogue."""
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import subprocess

from setup_core import PACKAGE, read_json
from setup_collection import check_tools
from gradle_audit import check_gradle


def find_mise_on_path(project):
    search_path = os.environ.get("PATH")
    if not search_path:
        return None
    # Windows can implicitly search the current directory. Only visit PATH entries.
    extensions = [""]
    if os.name == "nt":
        extensions = (os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD").split(";")
    for directory in search_path.split(os.pathsep):
        base = Path(project) / directory
        for extension in extensions:
            candidate = base / ("mise" + extension)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.absolute())
    return None


def check_mise(project):
    executable = find_mise_on_path(project)
    result = {
        "id": "mise", "required": True,
        "title": "mise is available on PATH and reports its version in the project's working environment",
        "status": "not_found", "executable": executable, "version": None,
        "evidence": {"command": None, "returncode": None, "stdout": "", "stderr": "", "error": None},
    }
    if executable is None:
        result["evidence"]["error"] = "mise was not found on PATH; check the existing installation before installing"
        return result

    evidence = result["evidence"]
    evidence["command"] = [executable, "--version"]
    result["status"] = "failed"
    if Path(executable).suffix.lower() in {".bat", ".cmd"}:
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


def mise_reader(project, mise):
    if mise["status"] != "satisfied":
        return None

    def execute(args):
        run = subprocess.run([mise["executable"], *args[1:]], cwd=project, check=True,
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        return run.stdout

    return execute


def check_java(project, execute, requested):
    result = {
        "id": "java", "required": True, "title": "Project JDK installed through mise",
        "requested_version": requested or None, "version": None, "status": "failed",
        "evidence": {},
    }
    evidence = result["evidence"]
    if not re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9-]*-)?\d+(?:u\d+)?(?:[._+-][A-Za-z0-9]+)*", requested):
        evidence["error"] = "Identify the JDK version from project sources"
        return result
    result["use_command"] = ["mise", "use", "--path", str(project), "java@" + requested]
    if execute is None:
        evidence["error"] = "Verify mise on PATH first"
        return result

    try:
        check_tools({"java": ["java", "javac"]}, project, execute)
        for binary in ("java", "javac"):
            evidence[binary] = execute(["mise", "which", binary, "--version"]).decode().strip()
        version = result["version"] = evidence["java"]
        # A major-only request accepts a patch of that major. Keep explicit vendor pins.
        observed = re.sub(r"^[A-Za-z][A-Za-z0-9-]*?-(?=\d)", "", version) if requested[0].isdigit() else version
        if evidence["javac"] == version and re.match(re.escape(requested) + r"(?:$|[._+-]|u\d)", observed):
            result["status"] = "satisfied"
        else:
            evidence["error"] = "The active Java runtime and compiler must match the project JDK"
    except subprocess.CalledProcessError as exc:
        evidence["error"] = exc.stderr.decode(errors="replace").strip() or str(exc)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        evidence["error"] = str(exc)
    return result


def audit_project(project_root, java_version):
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project-root must be an existing directory")
    requirements = [check_mise(project)]
    if java_version is not None:
        execute = mise_reader(project, requirements[0])
        requirements.append(check_java(project, execute, java_version))
        requirements.append(check_gradle(project, execute))
    tools = read_json(PACKAGE / "assets/recommended-tools.json")
    return {
        "project_root": str(project),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "system": platform.system(), "machine": platform.machine(),
        "requirements": requirements,
        "recommended_tools": [
            {"binary": binary, "tool_request": request,
             "use_command": ["mise", "use", "--path", str(project), request]}
            for binary, request in tools.items()
        ],
        "compliant": all(row["status"] == "satisfied" for row in requirements if row["required"]),
    }
