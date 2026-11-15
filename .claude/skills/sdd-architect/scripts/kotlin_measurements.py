"""Run the pinned metric implementation without constraining a project's Kotlin version."""

import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile


def collect_kotlin(sources, root, run, policy, *, java=None, detekt_jar=None):
    executable = str(Path(java).resolve()) if java else shutil.which("java")
    if not executable and os.environ.get("JAVA_HOME"):
        executable = str(Path(os.environ["JAVA_HOME"]) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    if not executable or not Path(executable).is_file():
        raise ValueError("Kotlin measurement needs a JDK: set JAVA_HOME or pass --java")
    cache = Path(os.environ.get("UV_TOOL_DIR", Path(tempfile.gettempdir()) / "uv-runtime" / "tools")) / "sdd-architect"
    jar = Path(detekt_jar).resolve() if detekt_jar else cache / "detekt-cli-1.23.8-all.jar"
    if not jar.is_file():
        if detekt_jar:
            raise ValueError(f"Configured detekt jar is missing: {jar}")
        cache.mkdir(parents=True, exist_ok=True)
        url = "https://repo.maven.apache.org/maven2/io/gitlab/arturbosch/detekt/detekt-cli/1.23.8/detekt-cli-1.23.8-all.jar"
        with tempfile.TemporaryDirectory(prefix="download-", dir=cache) as temporary:
            downloaded = Path(temporary) / jar.name
            with urllib.request.urlopen(url, timeout=policy["runtime"]["command_timeout_seconds"]) as response:
                with downloaded.open("wb") as output:
                    shutil.copyfileobj(response, output)
            downloaded.replace(jar)
    try:
        with zipfile.ZipFile(jar) as distribution:
            manifest_text = distribution.read("META-INF/MANIFEST.MF").decode("utf-8")
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError(f"Invalid detekt distribution: {jar}") from error
    manifest_fields = dict(line.split(": ", 1) for line in manifest_text.splitlines() if ": " in line)
    if manifest_fields.get("DetektVersion") != "1.23.8":
        raise ValueError("Kotlin metric profile requires detekt 1.23.8; use its CLI all.jar")
    with tempfile.TemporaryDirectory(prefix="sdd-kotlin-") as temporary:
        manifest = Path(temporary) / "files.txt"
        manifest.write_text("\n".join(path for path, source in sorted(sources.items()) if source["language"] == ".kt"), encoding="utf-8")
        argv = [executable, "--class-path", str(jar.resolve()), str(Path(__file__).with_name("KotlinMeasurements.java")),
                str(root), str(manifest)]
        return run(argv, root, policy), {"format": "kotlin-measurements", "tool": "detekt-metrics", "version": "1.23.8",
                                        "parser_version": manifest_fields.get("KotlinImplementationVersion"),
                                        "command": [executable, "--class-path", str(jar), "KotlinMeasurements.java", "<repository>", "<source-manifest>"]}
