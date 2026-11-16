#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build the two thin measurement plugins; dependencies and compiler output stay external."""

import sys
sys.dont_write_bytecode = True

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
BIN = ROOT.parents[1] / "skills/sdd-architect/bin"


def build(java_home, *, distributions=None):
    started = time.monotonic()
    metadata = json.loads((BIN / "plugins.json").read_text(encoding="utf-8"))
    cache = Path(os.environ.get("UV_TOOL_DIR", Path(tempfile.gettempdir()) / "uv-runtime/tools")) / "detekt-measurements"
    cache.mkdir(parents=True, exist_ok=True)
    compiler = Path(java_home) / "bin" / ("javac.exe" if os.name == "nt" else "javac")
    if not compiler.is_file():
        raise ValueError(f"JDK compiler not found: {compiler}")
    built = []
    with tempfile.TemporaryDirectory(prefix="detekt-plugin-build-") as temporary:
        work = Path(temporary)
        for major, adapter in metadata["adapters"].items():
            version = adapter["minimum_version"]
            distribution = Path((distributions or {}).get(major) or cache / f"detekt-cli-{version}-all.jar")
            if not distribution.is_file():
                if (distributions or {}).get(major):
                    raise ValueError(f"Build dependency does not exist: {distribution}")
                group = "io/gitlab/arturbosch/detekt" if major == "1" else "dev/detekt"
                url = f"https://repo.maven.apache.org/maven2/{group}/detekt-cli/{version}/detekt-cli-{version}-all.jar"
                print(f"Build dependency: detekt {version}", flush=True)
                download = work / f"detekt-{major}.jar"
                with urllib.request.urlopen(url, timeout=max(1, 110 - (time.monotonic() - started))) as response:
                    with download.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            if time.monotonic() - started > 110:
                                raise TimeoutError("Plugin build exceeded its 110-second budget")
                download.replace(distribution)
            classes = work / f"classes-{major}"
            classes.mkdir()
            sources = sorted((ROOT / "common/src").rglob("*.java")) + sorted((ROOT / f"detekt{major}/src").rglob("*.java"))
            generated = work / "MeasurementMetadata.java"
            generated.write_text(
                "package dev.aisdlc.detekt;\nfinal class MeasurementMetadata {\n"
                f"static final int SCHEMA_VERSION = {int(metadata['schema_version'])};\n"
                f"static final String PROFILE = {json.dumps(metadata['measurement_profile'])};\n"
                f"static final String PLUGIN_VERSION = {json.dumps(metadata['plugin_version'])};\n"
                "}\n", encoding="utf-8")
            sources.append(generated)
            arguments = ["--release", "17", "-encoding", "UTF-8", "-classpath", str(distribution), "-d", str(classes),
                         *map(str, sources)]
            argument_file = work / f"javac-{major}.args"
            argument_file.write_text("\n".join('"' + argument.replace('\\', '\\\\').replace('"', '\\"') + '"'
                                                for argument in arguments), encoding="utf-8")
            process = subprocess.Popen([str(compiler), "@" + str(argument_file)], shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            try:
                stdout, stderr = process.communicate(timeout=max(1, 110 - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False,
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    process.kill()
                process.communicate()
                raise TimeoutError("Plugin build exceeded its 110-second budget") from None
            if process.returncode:
                raise ValueError(stderr.decode("utf-8", errors="replace"))
            jar = work / adapter["jar"]
            resources = ROOT / f"detekt{major}/resources"
            entries = {path.relative_to(classes).as_posix(): path.read_bytes() for path in classes.rglob("*.class")}
            entries.update({path.relative_to(resources).as_posix(): path.read_bytes() for path in resources.rglob("*") if path.is_file()})
            entries["META-INF/MANIFEST.MF"] = (
                "Manifest-Version: 1.0\nImplementation-Title: sdd-architect measurements\n"
                f"Implementation-Version: {metadata['plugin_version']}\nDetekt-Minimum-Version: {version}\n"
                f"Detekt-Major-Version: {major}\n\n").encode()
            with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in sorted(entries.items()):
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, data)
            built.append((jar, BIN / adapter["jar"]))
        # Publish only after both adapters compile; bin is an explicitly requested deliverable.
        for source, destination in built:
            destination.write_bytes(source.read_bytes())
    return {"jars": [str(destination) for _, destination in built], "elapsed_seconds": time.monotonic() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--detekt1-jar", type=Path)
    parser.add_argument("--detekt2-jar", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.java_home, distributions={"1": args.detekt1_jar, "2": args.detekt2_jar})))
    except (OSError, ValueError, TimeoutError) as error:
        print(f"detekt-measurements: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
