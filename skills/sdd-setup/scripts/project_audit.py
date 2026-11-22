"""Read-only checks of project requirements; remediation belongs to the dialogue."""
from datetime import datetime, timezone
from http.client import HTTPException
import os
from pathlib import Path
import platform
import re
import subprocess
from urllib.request import urlopen
from xml.etree import ElementTree

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
        run = subprocess.run([mise["executable"], *args[1:]], cwd=project, check=True, shell=False,
                             env={**os.environ, "MISE_AUTO_INSTALL": "false"},
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        return run.stdout

    return execute


def check_java(project, execute, requested, build=None):
    result = {
        "id": "java", "required": True, "title": "Project JDK installed through mise",
        "requested_version": requested or None, "version": None, "status": "failed",
        "evidence": {},
    }
    evidence = result["evidence"]
    if not re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9-]*-)?\d+(?:u\d+)?(?:[._+-][A-Za-z0-9]+)*", requested):
        evidence["error"] = "Identify the JDK version from project sources"
        return result
    result["use_command"] = ["mise", "use", "--path", str(build or project), "java@" + requested]
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


def check_required_tools(project, execute):
    requirements = []
    for binary, request in read_json(PACKAGE / "assets/required-tools.json").items():
        evidence = {}
        row = {"id": binary, "title": f"Project {binary} installed through mise", "required": True,
               "tool_request": request, "use_command": ["mise", "use", "--path", str(project), request],
               "status": "unverified", "version": None, "evidence": evidence}
        requirements.append(row)
        if execute is None:
            evidence["error"] = "Verify mise on PATH first"
            continue
        try:
            provider = execute(["mise", "which", binary, "--plugin"]).decode().strip()
            evidence["provider"] = provider
            check_tools({provider: [binary]}, project, execute)
            version = execute(["mise", "which", binary, "--version"]).decode().strip()
            if not version:
                raise ValueError(f"mise returned no active version for {binary}")
            row["version"] = version
            evidence["output"] = execute(["mise", "exec", "--", binary, "--version"]).decode(errors="replace").strip()
            if not evidence["output"]:
                raise ValueError(f"{binary} --version returned no output")
            row["status"] = "satisfied"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            row["status"] = "failed"
            stderr = getattr(exc, "stderr", None)
            evidence["error"] = stderr.decode(errors="replace").strip() if stderr else str(exc)
    return requirements


ARCHUNIT_METADATA = "https://repo.maven.apache.org/maven2/com/tngtech/archunit/archunit/maven-metadata.xml"


def dependency_evidence(tool, observations):
    dependencies = []
    for version, source in observations:
        if not version.strip() or not source.strip():
            raise ValueError(f"Provide the observed {tool} version or 'missing', and its evidence")
        dependencies.append({"version": version, "source": source})
    return dependencies


def dependency_status(dependencies, matches):
    known = [dep["version"] for dep in dependencies if dep["version"] != "unverified"]
    if any(not matches(version) for version in known):
        return "failed"
    if known and len(known) == len(dependencies):
        return "satisfied"
    return "unverified"


def check_junit(observations):
    dependencies = dependency_evidence("JUnit", observations)
    return {"id": "junit", "required": True, "title": "JVM tests use JUnit Jupiter 5",
            "status": dependency_status(dependencies, lambda v: re.fullmatch(r"5\.\d+\.\d+(?:[-+][\w.-]+)?", v)),
            "evidence": {"dependencies": dependencies}}


def check_jacoco(modules, observations):
    expected = set(modules)
    if len(expected) != len(modules) or any(not module.strip() for module in expected):
        raise ValueError("Provide distinct nonempty --jacoco-module paths from the build")
    observed = {}
    for module, status, source in observations:
        if module not in expected or module in observed:
            raise ValueError(f"Unexpected or repeated JaCoCo module: {module}")
        if status not in {"satisfied", "failed", "unverified"} or not source.strip():
            raise ValueError(f"Provide a JaCoCo check status and evidence for {module}")
        observed[module] = {"status": status, "source": source}
    missing = sorted(expected.difference(observed))
    statuses = {row["status"] for row in observed.values()}
    status = "unverified"
    if "failed" in statuses:
        status = "failed"
    elif not missing and statuses == {"satisfied"}:
        status = "satisfied"
    return {"id": "jacoco", "required": True, "title": "JaCoCo coverage of all JVM modules",
            "status": status, "evidence": {"observations": observed, "missing_modules": missing}}


def check_archunit(observations):
    dependencies = dependency_evidence("ArchUnit", observations)
    evidence = {"release_source": ARCHUNIT_METADATA, "dependencies": dependencies}
    result = {"id": "archunit", "required": True, "title": "Latest stable ArchUnit test dependency",
              "status": "unverified", "latest_stable": None, "evidence": evidence}
    if any(dep["version"] == "missing" for dep in dependencies):
        result["status"] = "failed"
    try:
        with urlopen(ARCHUNIT_METADATA, timeout=5) as response:
            metadata = ElementTree.parse(response)
        if (metadata.findtext("groupId"), metadata.findtext("artifactId")) != ("com.tngtech.archunit", "archunit"):
            raise ValueError("Unexpected ArchUnit Maven metadata")
        versions = [v.text for v in metadata.findall("versioning/versions/version")
                    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", v.text or "")]
        if not versions:
            raise ValueError("No stable ArchUnit version found in Maven Central")
        latest = max(versions, key=lambda value: tuple(map(int, value.split("."))))
    except (OSError, HTTPException, ElementTree.ParseError, ValueError) as exc:
        evidence["release_error"] = str(exc)
        return result
    result["latest_stable"] = latest
    result["status"] = dependency_status(dependencies, lambda version: version == latest)
    return result


def resolve_build(project, build_root):
    if not build_root:
        return project
    build = (project / build_root).resolve(strict=True)
    if not build.is_dir() or not build.is_relative_to(project):
        raise ValueError("--build-root must be a JVM build directory inside the project")
    return build


def audit_jvm_step(step, project_root, build_root=None, jdk="", observation=(), jacoco_modules=(), jacoco=()):
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project-root must be an existing directory")
    build = resolve_build(project, build_root)
    if step == "junit5":
        return check_junit(observation)
    if step == "jacoco":
        return check_jacoco(jacoco_modules, jacoco)
    if step == "archunit":
        return check_archunit(observation)
    execute = mise_reader(build, check_mise(build))
    if step == "jdk":
        return check_java(project, execute, jdk, build)
    if step == "gradle":
        return check_gradle(build, execute, project_root=project)
    raise ValueError(f"Unknown JVM step: {step}")


def audit_project(project_root, java_version, ktlint=(), detekt=(), build_root=None, archunit=(), junit=(),
                  jacoco_modules=(), jacoco=()):
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project-root must be an existing directory")
    if (archunit or junit or jacoco_modules or jacoco) and java_version is None:
        raise ValueError("JUnit, JaCoCo and ArchUnit observations require a JVM build")
    if build_root and java_version is None:
        raise ValueError("--build-root requires a JVM build")
    build = resolve_build(project, build_root)
    requirements = [check_mise(project)]
    execute = mise_reader(project, requirements[0])
    requirements.extend(check_required_tools(project, execute))
    ready = all(row["status"] == "satisfied" for row in requirements)
    if java_version is not None and ready:
        build_reader = mise_reader(build, requirements[0])
        requirements.append(check_java(project, build_reader, java_version, build))
        requirements.append(check_gradle(build, build_reader, project_root=project))
        requirements.append(check_junit(junit))
        requirements.append(check_jacoco(jacoco_modules, jacoco))
        requirements.append(check_archunit(archunit))
    for tool, observations in (("ktlint", ktlint), ("detekt", detekt)):
        for scope, status, observation in observations:
            if status not in {"satisfied", "failed", "unverified"} or not scope.strip() or not observation.strip():
                raise ValueError(f"Provide {tool} scope, satisfied/failed/unverified status and evidence")
            requirements.append({"id": tool, "scope": scope, "required": True, "title": f"Project {tool} integration",
                                 "status": status, "evidence": {"observation": observation}})
    return {
        "project_root": str(project),
        "build_root": str(build) if java_version is not None else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "system": platform.system(), "machine": platform.machine(),
        "requirements": requirements,
        "compliant": all(row["status"] == "satisfied" for row in requirements if row["required"]),
    }
