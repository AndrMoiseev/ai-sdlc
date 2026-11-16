"""Select a thin plugin and invoke the detekt runtime already chosen by the project."""

import json
import os
from pathlib import Path
import re
import shutil

BIN = Path(__file__).resolve().parents[1] / "bin"
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*))?(?:\+[0-9A-Za-z.-]+)?")


def plugin_metadata():
    return json.loads((BIN / "plugins.json").read_text(encoding="utf-8"))


def version_key(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Unrecognized detekt version: {version!r}")
    major, minor, patch, prerelease = match.groups()
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part) for part in (prerelease or "").split("."))
    return (int(major), int(minor), int(patch), (0, identifiers) if prerelease else (1, ()))


def select_plugin(version):
    key = version_key(version)
    adapter = plugin_metadata()["adapters"].get(str(key[0]))
    if not adapter:
        raise ValueError(f"Unsupported detekt major {key[0]}; available measurement adapters: 1, 2")
    if key < version_key(adapter["minimum_version"]):
        raise ValueError(f"detekt {version} is below the adapter minimum {adapter['minimum_version']}")
    return {**adapter, "path": BIN / adapter["jar"], "input_separator": "," if key[0] == 1 else os.pathsep}


def java_executable(java=None):
    executable = str(Path(java).resolve()) if java else shutil.which("java")
    if not executable and os.environ.get("JAVA_HOME"):
        executable = str(Path(os.environ["JAVA_HOME"]) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    if not executable or not Path(executable).is_file():
        raise ValueError("Kotlin measurements need JDK 17+: set JAVA_HOME or pass --java")
    return executable


def java_arguments(arguments):
    """Java launcher argument files avoid Windows command-length and shell-quoting limits."""
    return "\n".join('"' + str(argument).replace('\\', '\\\\').replace('"', '\\"')
                     .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"'
                     for argument in arguments) + "\n"


def invoke_java(executable, arguments, root, run, policy, temporary, name):
    argument_file = temporary / f"{name}.args"
    argument_file.write_text(java_arguments(arguments), encoding="utf-8")
    return run([executable, "@" + str(argument_file)], root, policy)


def resolve_runtime(root, executable, run, policy, temporary, *, detekt_jar=None, detekt_project=":"):
    if detekt_jar:
        jar = Path(detekt_jar).resolve()
        if not jar.is_file():
            raise ValueError(f"Existing detekt CLI distribution not found: {jar}")
        arguments = ["-jar", str(jar)]
        declared = None
        origin = "existing-cli"
    else:
        if not re.fullmatch(r":(?:[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)*)?", detekt_project):
            raise ValueError("--detekt-project must be a Gradle project path such as : or :server")
        wrapper = root / "gradle/wrapper/gradle-wrapper.jar"
        if not wrapper.is_file():
            raise ValueError("No Gradle wrapper; provide the existing detekt CLI with --detekt-jar")
        descriptor = temporary / "detekt-runtime.json"
        init_script = Path(__file__).with_name("detekt-runtime.init.gradle")
        invoke_java(executable, [
            f"-Dsdd.architect.detekt.project={detekt_project}",
            f"-Dsdd.architect.detekt.runtime={descriptor}",
            "-classpath", str(wrapper), "org.gradle.wrapper.GradleWrapperMain",
            "--no-daemon", "--no-configuration-cache", "--console=plain",
            "--project-cache-dir", str(temporary / "gradle-cache"),
            "--init-script", str(init_script), ":sddArchitectDetektRuntime",
        ], root, run, policy, temporary, "gradle-runtime")
        if not descriptor.is_file():
            raise ValueError("Gradle did not export its configured detekt runtime")
        value = json.loads(descriptor.read_text(encoding="utf-8"))
        declared = value["version"]
        adapter = select_plugin(declared)
        if value["main_class"] != adapter["main_class"]:
            raise ValueError("Configured detekt entry point disagrees with its version")
        classpath = value["classpath"]
        if not classpath or any(not Path(path).is_file() for path in classpath):
            raise ValueError("Configured detekt classpath contains missing files")
        arguments = ["-classpath", os.pathsep.join(classpath), adapter["main_class"]]
        origin = f"gradle:{detekt_project}"
    output = invoke_java(executable, [*arguments, "--version"], root, run, policy, temporary, "detekt-version").decode("utf-8").strip()
    # --version is the runtime authority; do not infer from a filename or cached audit.
    versions = [match.group() for match in VERSION.finditer(output)]
    if len(versions) != 1:
        raise ValueError(f"Expected one detekt --version value, received: {output!r}")
    version = versions[0]
    if declared is not None and version != declared:
        raise ValueError(f"Configured detekt {declared} launches as {version}")
    adapter = select_plugin(version)
    if not adapter["path"].is_file():
        raise ValueError(f"Bundled measurement plugin is missing: {adapter['path']}")
    return {"arguments": arguments, "version": version, "adapter": adapter, "origin": origin}
