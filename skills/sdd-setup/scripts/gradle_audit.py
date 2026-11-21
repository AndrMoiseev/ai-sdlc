"""Read-only Gradle configuration and stable release checks."""
from http.client import HTTPException
import json
import os
import re
import subprocess
from urllib.request import urlopen

from setup_collection import check_tools


CURRENT_RELEASE = "https://services.gradle.org/versions/current"


def gradle_wrapper(project):
    launcher = project / ("gradlew.bat" if os.name == "nt" else "gradlew")
    directory = project / "gradle/wrapper"
    properties = directory / "gradle-wrapper.properties"
    files = [launcher, directory / "gradle-wrapper.jar", properties]
    missing = [str(path.relative_to(project)) for path in files if not path.is_file() or not path.stat().st_size]
    if missing:
        return {"status": "incomplete" if len(missing) < len(files) else "not_found", "missing": missing}
    if os.name != "nt" and not os.access(launcher, os.X_OK):
        return {"status": "incomplete", "error": "gradlew is not executable"}
    # Last assignment wins in a Java properties file. Keep private mirror URLs out of the report.
    settings = properties.read_text(encoding="latin-1")
    urls = re.findall(r"^[ \t]*distributionUrl(?:[ \t]*[=:][ \t]*|[ \t]+)([^\r\n]*)", settings, re.M)
    if not urls or not urls[-1].strip():
        return {"status": "incomplete", "error": "Missing distributionUrl"}
    archive = re.split(r"[?#]", urls[-1].strip(), maxsplit=1)[0].rsplit("/", 1)[-1]
    version = re.fullmatch(r"gradle-(\d+(?:\.\d+)+(?:-[\w.-]+)?)-(?:bin|all)\.zip", archive)
    return {"status": "configured", "version": version[1] if version else None,
            "launcher": str(launcher.relative_to(project))}


def newer_stable(current, stable):
    # A stable release also succeeds its own RC, milestone, or nightly.
    parsed = re.fullmatch(r"(\d+(?:\.\d+)+)(?:-([\w.-]+))?", current)
    if not parsed:
        return False
    def parts(version):
        return tuple(map(int, re.sub(r"(?:\.0)+$", "", version).split(".")))
    installed, candidate = parts(parsed[1]), parts(stable)
    preview = re.fullmatch(r"(?:rc-\d+|milestone-\d+|\d{8,}.*|SNAPSHOT)", parsed[2] or "", re.I)
    return candidate > installed or (candidate == installed and preview is not None)


def stable_gradle_release():
    with urlopen(CURRENT_RELEASE, timeout=5) as response:
        release = json.load(response)
    if not (isinstance(release, dict) and release.get("current") is True
            and isinstance(release.get("version"), str) and re.fullmatch(r"\d+(?:\.\d+)+", release["version"])
            and not any(release.get(flag) for flag in ("broken", "snapshot", "nightly", "releaseNightly",
                                                       "activeRc", "rcFor", "milestoneFor"))):
        raise ValueError("Could not confirm the current stable Gradle release")
    return release["version"]


def check_gradle(project, execute):
    try:
        wrapper = gradle_wrapper(project)
    except OSError as exc:
        wrapper = {"status": "failed", "error": str(exc)}
    mise = {"status": "unverified"}
    if execute is not None:
        try:
            provider = execute(["mise", "which", "gradle", "--plugin"]).decode().strip()
            check_tools({provider: ["gradle"]}, project, execute)
            version = execute(["mise", "which", "gradle", "--version"]).decode().strip()
            if not version:
                raise ValueError("mise returned no Gradle version")
            mise = {"status": "configured", "version": version, "provider": provider}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            mise = {"status": "unverified", "error": str(exc)}
    methods = {"wrapper": wrapper, "mise": mise}
    configured = [method for method in methods.values() if method["status"] == "configured"]
    versions = {method["version"] for method in configured}
    result = {"id": "gradle", "required": True, "title": "Project Gradle Wrapper or mise installation",
              "status": "satisfied" if configured else "failed", "evidence": methods,
              "version": versions.pop() if len(versions) == 1 else None}
    if any(method["version"] for method in configured):
        try:
            stable = stable_gradle_release()
            result["latest_stable"] = stable
            for method in configured:
                if method["version"] and newer_stable(method["version"], stable):
                    method["suggested_version"] = stable
        except (OSError, ValueError, HTTPException) as exc:
            result["release_error"] = str(exc)
    return result
