import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from analysis_policy import load_policy
from collection import run
from detekt_runtime import BIN, java_arguments, plugin_metadata, resolve_runtime, select_plugin, version_key
from kotlin_measurements import collect_kotlin
from quality_indicators import qualify_kotlin


POLICY = load_policy()


class PluginSelectionTests(unittest.TestCase):
    def test_minimum_versions_and_future_releases_in_supported_majors(self):
        for version, expected in (("1.23.8", "1"), ("1.24.0", "1"), ("2.0.0-alpha.6", "2"),
                                  ("2.0.0-alpha.10", "2"), ("2.0.0-beta.1", "2"), ("2.0.0", "2"),
                                  ("2.9.0+build.3", "2")):
            with self.subTest(version=version):
                self.assertEqual(select_plugin(version)["jar"], f"detekt-measurements-{expected}.jar")
        for version in ("1.23.7", "1.23.8-RC1", "2.0.0-alpha.5", "0.9.0", "3.0.0", "2.0", "garbage"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                select_plugin(version)
        self.assertLess(version_key("2.0.0-alpha.9"), version_key("2.0.0-alpha.10"))

    def test_argument_file_escapes_shell_metacharacters_as_data(self):
        self.assertEqual(java_arguments(['C:\\space & $name\\one"two', "--input", "@a"]),
                         '"C:\\\\space & $name\\\\one\\"two"\n"--input"\n"@a"\n')

    def test_import_checks_methodology_and_minimum_without_exact_runtime_pin(self):
        raw = {"format": "kotlin-measurements", "version": 2, "measurement_profile": "kotlin-tokens-functions-1",
               "complete": True, "tool_version": "2.4.0", "files": []}
        self.assertEqual(qualify_kotlin(raw, {}), {})
        for key, value in (("version", 1), ("measurement_profile", "other"), ("complete", False),
                           ("tool_version", "2.0.0-alpha.1")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                qualify_kotlin({**raw, key: value}, {})

    def test_runtime_version_probe_rejects_ambiguous_or_unsupported_output(self):
        for output in (b"2.0.0 and 2.1.0", b"unknown", b"1.23.0", b"3.0.0"):
            with self.subTest(output=output), patch.object(Path, "is_file", return_value=True), \
                    patch("detekt_runtime.invoke_java", return_value=output), self.assertRaises(ValueError):
                resolve_runtime(Path("repository"), "java", None, POLICY, Path("temporary"), detekt_jar="detekt.jar")

    def test_gradle_descriptor_must_match_actual_runtime(self):
        descriptor = {"version": "2.0.0-alpha.6", "classpath": ["detekt.jar"], "main_class": "dev.detekt.cli.Main"}
        metadata = plugin_metadata()
        with patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "read_text", return_value=json.dumps(descriptor)), \
                patch("detekt_runtime.plugin_metadata", return_value=metadata), \
                patch("detekt_runtime.invoke_java", side_effect=[b"", b"2.1.0"]), self.assertRaisesRegex(ValueError, "launches as"):
            resolve_runtime(Path("repository"), "java", None, POLICY, Path("temporary"))

    def test_packaged_plugins_are_thin_and_registered_for_their_host_api(self):
        # Reading the delivered archives is necessary to detect accidental compiler/API bundling
        # and missing ServiceLoader descriptors; source-level mocks cannot validate the deliverable.
        for major, adapter in plugin_metadata()["adapters"].items():
            with self.subTest(major=major), zipfile.ZipFile(BIN / adapter["jar"]) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("KotlinMeasurements.class") for name in names))
                self.assertFalse(any(name.startswith(("kotlin/", "org/jetbrains/", "com/intellij/", "dev/detekt/", "io/gitlab/")) for name in names))
                api = "io.gitlab.arturbosch.detekt.api" if major == "1" else "dev.detekt.api"
                for interface in ("FileProcessListener", "OutputReport"):
                    self.assertIn(f"META-INF/services/{api}.{interface}", names)


class PluginIntegrationTests(unittest.TestCase):
    def test_existing_gradle_subproject_runtime_is_used_without_build_edits(self):
        # Risk: Gradle init-script evaluation and resolved configuration export cannot be
        # validated by a mocked descriptor. One real subproject covers that integration.
        wrapper = os.environ.get("ARCHITECT_TEST_GRADLE_WRAPPER")
        self.assertTrue(wrapper, "Set ARCHITECT_TEST_GRADLE_WRAPPER to an existing wrapper jar")
        java = os.environ.get("ARCHITECT_TEST_JAVA")
        self.assertTrue(java, "Set ARCHITECT_TEST_JAVA to JDK 17+")
        with tempfile.TemporaryDirectory(prefix="architect gradle space-") as directory:
            root = Path(directory)
            (root / "gradle/wrapper").mkdir(parents=True)
            wrapper = Path(wrapper)
            for name in ("gradle-wrapper.jar", "gradle-wrapper.properties"):
                shutil.copyfile(wrapper.with_name(name), root / "gradle/wrapper" / name)
            (root / "settings.gradle").write_text("rootProject.name = 'measurements'\ninclude('analysis')\n", encoding="utf-8")
            module = root / "analysis"
            module.mkdir()
            version = plugin_metadata()["adapters"]["2"]["minimum_version"]
            build = f'''repositories {{ mavenCentral() }}
configurations {{ detekt }}
dependencies {{ detekt 'dev.detekt:detekt-cli:{version}' }}
'''
            (module / "build.gradle").write_text(build, encoding="utf-8")
            (root / "A.kt").write_text("context(_: String)\nfun configured() = 1\n", encoding="utf-8")
            sources = {"A.kt": {"language": ".kt", "package": ""}}
            data, metadata = collect_kotlin(sources, root, run, POLICY, java=java, detekt_project=":analysis")
            self.assertEqual(metadata["runtime"], "gradle::analysis")
            self.assertEqual(metadata["version"], version)
            self.assertEqual(len(qualify_kotlin(json.loads(data), sources)["A.kt"]["functions"]), 1)
            self.assertEqual((module / "build.gradle").read_text(encoding="utf-8"), build)
            self.assertFalse((root / ".gradle").exists())

    def test_both_host_apis_complete_population_and_new_context_parameter_syntax(self):
        # Risk: only actual detekt runs detect SPI/classloader/PSI ABI failures and the original
        # context-parameter parse failure. Two hosts are necessary; rule combinations stay unit tests.
        java = os.environ.get("ARCHITECT_TEST_JAVA")
        self.assertTrue(java, "Set ARCHITECT_TEST_JAVA to JDK 17+")
        for major in ("1", "2"):
            jar = os.environ.get(f"ARCHITECT_TEST_DETEKT{major}_JAR")
            self.assertTrue(jar, f"Set ARCHITECT_TEST_DETEKT{major}_JAR")
            with self.subTest(major=major), tempfile.TemporaryDirectory(prefix="architect plugin space-") as directory:
                root = Path(directory)
                code = '''package example
import kotlin.math.abs
@Suppress("CognitiveComplexMethod")
fun zero() = 0
fun outer(x: Int): Int {
    fun inner(y: Int) = if (y > 0) y else 0
    return inner(x)
}
class A { fun value() = "λ😀" }
'''
                code += ("context(String)\nfun contextual() = 1\n" if major == "1" else
                         "context(_: String)\nfun contextual() = 1\ncontext(value: String)\nfun namedContext() = value.length\n")
                (root / "A.kt").write_bytes(code.replace("\n", "\r\n").encode("utf-8"))
                (root / "Empty.kt").write_text("// no functions\n", encoding="utf-8")
                sources = {"A.kt": {"language": ".kt", "package": "example"},
                           "Empty.kt": {"language": ".kt", "package": ""}}
                data, metadata = collect_kotlin(sources, root, run, POLICY, java=java, detekt_jar=jar)
                value = json.loads(data)
                files = qualify_kotlin(value, sources)
                self.assertEqual(value["tool_version"], metadata["version"])
                self.assertEqual(value["plugin_version"], plugin_metadata()["plugin_version"])
                self.assertTrue(value["parser_version"])
                self.assertEqual(select_plugin(metadata["version"])["jar"], f"detekt-measurements-{major}.jar")
                self.assertEqual(files["Empty.kt"]["tokens"], [])
                row = files["A.kt"]
                functions = {function["signature"]: function for function in row["functions"]}
                self.assertEqual(functions["zero()"]["cognitive_complexity"], 0)
                self.assertEqual(functions["inner(Int)"]["cognitive_complexity"], 2)
                self.assertEqual(sum(function["nested"] for function in functions.values()), 1)
                self.assertIn("contextual()", functions)
                if major == "2":
                    self.assertIn("namedContext()", functions)
                self.assertTrue(any(container["kind"] == "class" for container in row["containers"]))
                self.assertFalse(any(token["text"] in {"package", "import"} for token in row["tokens"]))
                encoded = code.encode("utf-16-le")
                for token in row["tokens"]:
                    self.assertEqual(encoded[token["start"] * 2:token["end"] * 2].decode("utf-16-le"), token["text"])
                # A successful host invocation above isolates this failure to malformed input;
                # the processor must not turn parser recovery into a complete measurement report.
                (root / "Broken.kt").write_text("fun broken( {", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "invalid Kotlin syntax"):
                    collect_kotlin({"Broken.kt": {"language": ".kt", "package": ""}},
                                   root, run, POLICY, java=java, detekt_jar=jar)


if __name__ == "__main__":
    unittest.main()
