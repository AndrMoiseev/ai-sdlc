"""Collect complete Kotlin measurements through a plugin in the project's existing detekt."""

import json
from pathlib import Path
import tempfile

from detekt_runtime import invoke_java, java_executable, plugin_metadata, resolve_runtime


def collect_kotlin(sources, root, run, policy, *, java=None, detekt_jar=None, detekt_project=":"):
    root = Path(root).resolve()
    executable = java_executable(java)
    paths = sorted(path for path, source in sources.items() if source["language"] == ".kt")
    for path in paths:
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"Kotlin input is missing or outside repository: {path}")
        if any(character in str(resolved) for character in ("\n", "\r")):
            raise ValueError(f"detekt CLI input cannot contain newlines: {path}")
    with tempfile.TemporaryDirectory(prefix="sdd-detekt-") as directory:
        temporary = Path(directory)
        runtime = resolve_runtime(root, executable, run, policy, temporary,
                                  detekt_jar=detekt_jar, detekt_project=detekt_project)
        separator = runtime["adapter"]["input_separator"]
        if any(separator in str(root / path) for path in paths):
            raise ValueError(f"detekt CLI input paths cannot contain its separator {separator!r}")
        metadata = plugin_metadata()
        manifest = temporary / "sources.txt"
        manifest.write_text("\n".join(paths), encoding="utf-8")
        output = temporary / "measurements.json"
        properties = [f"-Dsdd.architect.repository={root}", f"-Dsdd.architect.sourceManifest={manifest}",
                      f"-Dsdd.architect.detekt.version={runtime['version']}"]
        arguments = [*properties, *runtime["arguments"],
                     "--input", separator.join(str(root / path) for path in paths) if paths else str(temporary / "empty"),
                     "--plugins", str(runtime["adapter"]["path"]), "--disable-default-rulesets",
                     "--report", f"sdd-architect-measurements:{output}"]
        if not paths:
            (temporary / "empty").mkdir()
        invoke_java(executable, arguments, root, run, policy, temporary, "detekt-measurements")
        if not output.is_file():
            raise ValueError("detekt did not produce the measurement report; check plugin/report activation")
        data = output.read_bytes()
        value = json.loads(data)
        if (value.get("version") != metadata["schema_version"]
                or value.get("measurement_profile") != metadata["measurement_profile"]
                or value.get("tool_version") != runtime["version"]):
            raise ValueError("detekt measurement report disagrees with the selected runtime or measurement profile")
        return data, {"format": "kotlin-measurements", "tool": "detekt", "version": runtime["version"],
                      "parser_version": value.get("parser_version"), "plugin_version": value.get("plugin_version"),
                      "measurement_profile": value["measurement_profile"], "runtime": runtime["origin"],
                      "command": [executable, "<existing-detekt-runtime>", "--input", "<source-inventory>",
                                  "--plugins", runtime["adapter"]["jar"], "--report", "sdd-architect-measurements:<report>"]}
