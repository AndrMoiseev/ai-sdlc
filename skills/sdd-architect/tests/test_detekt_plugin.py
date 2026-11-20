import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from analysis_policy import load_policy
from collection import run
from detekt_runtime import BIN, plugin_metadata, select_plugin, version_key
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

    def test_import_checks_methodology_and_minimum_without_exact_runtime_pin(self):
        raw = {"format": "kotlin-measurements", "version": 2, "measurement_profile": "kotlin-tokens-functions-1",
               "complete": True, "tool_version": "2.4.0", "files": []}
        self.assertEqual(qualify_kotlin(raw, {}), {})
        for key, value in (("version", 1), ("measurement_profile", "other"), ("complete", False),
                           ("tool_version", "2.0.0-alpha.1")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                qualify_kotlin({**raw, key: value}, {})

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


def plugin_report(sources, root, java, jar, version):
    # Developer ABI fixture. Production collection only invokes the project task.
    manifest = root / "sources.txt"
    manifest.write_text("\n".join(sources), encoding="utf-8")
    output = root / "measurements.json"
    sarif = root / "detekt.sarif"
    config = root / "detekt.yml"
    config.write_text("complexity:\n  active: true\n  LongParameterList:\n    active: true\n", encoding="utf-8")
    separator = "," if version.startswith("1.") else os.pathsep
    run([java, f"-Dsdd.architect.repository={root}", f"-Dsdd.architect.sourceManifest={manifest}",
         f"-Dsdd.architect.detekt.version={version}", "-jar", jar, "--input",
         separator.join(str(root / name) for name in sources), "--plugins", str(BIN / select_plugin(version)["jar"]),
         "--config", str(config), "--report", f"sarif:{sarif}",
         "--report", f"sdd-architect-measurements:{output}"], root, POLICY)
    if not json.loads(sarif.read_bytes())["runs"]:
        raise AssertionError("The project detekt run must also produce a SARIF report")
    return json.loads(output.read_bytes())


class PluginIntegrationTests(unittest.TestCase):
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
                version = plugin_metadata()["adapters"][major]["minimum_version"]
                value = plugin_report(sources, root, java, jar, version)
                files = qualify_kotlin(value, sources)
                self.assertEqual(value["tool_version"], version)
                self.assertEqual(value["plugin_version"], plugin_metadata()["plugin_version"])
                self.assertTrue(value["parser_version"])
                self.assertEqual(select_plugin(version)["jar"], f"detekt-measurements-{major}.jar")
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
                    plugin_report(["Broken.kt"], root, java, jar, version)


if __name__ == "__main__":
    unittest.main()
