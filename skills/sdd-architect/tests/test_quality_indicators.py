import json
import math
import re
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from analysis_policy import load_policy
from collection import collect, map_classes
from design_rule_hierarchy import decoupling_level, hierarchy, structural_metrics
from project_status import publish_status, render_status
from quality_indicators import coverage_methods, coverage_summary, duplication, indicators, maintainability, qualify_kotlin


POLICY = load_policy()
PARAMETERS = POLICY["measurements"]["quality_indicators"]


def file_row(path, package="example", count=10, complexity=0, texts=None):
    return {"file": path, "package": package,
            "tokens": [{"start": index * 2, "end": index * 2 + 1, "type": "ID", "text": token}
                       for index, token in enumerate(texts if texts is not None else [str(n) for n in range(count)])],
            "functions": [{"start": 0, "end": count * 2, "cognitive_complexity": complexity,
                           "nested": False, "signature": "f()", "owner": ""}],
            "containers": [{"kind": "function", "start": 0, "end": count * 2}]}


def kotlin(rows):
    return {"format": "kotlin-measurements", "version": 2, "complete": True,
            "measurement_profile": "kotlin-tokens-functions-1",
            "tool_version": "1.23.8", "files": rows}


def jacoco(*, with_lines=True):
    lines = ('''<line nr="3" ci="1" mi="2"/><line nr="17" ci="0" mi="2"/>
      <counter type="LINE" covered="1" missed="1"/>''' if with_lines else "")
    return f'''<report name="test"><package name="example"><class name="example/A" sourcefilename="A.kt">
      <method name="f" desc="()I"><counter type="INSTRUCTION" covered="5" missed="5"/>
      <counter type="BRANCH" covered="2" missed="2"/><counter type="COMPLEXITY" covered="2" missed="2"/></method>
      <method name="g" desc="()I"><counter type="INSTRUCTION" covered="8" missed="2"/>
      <counter type="COMPLEXITY" covered="8" missed="2"/></method></class>
      <sourcefile name="A.kt">{lines}</sourcefile>
      </package></report>'''


class QualityTests(unittest.TestCase):
    def test_explicit_class_mapping_resolves_ambiguous_sourcefile(self):
        sources = {path: {"package": "example"} for path in ("left/A.kt", "right/A.kt")}
        with (
            patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path),
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "rglob", return_value=[Path("A.class")]),
            patch.object(Path, "read_bytes", return_value=b"fixture"),
            patch("collection.class_source_file", return_value=("example.A", "A.kt")),
        ):
            mappings, gaps = map_classes({"class_directories": ["classes"],
                "class_files": {"example.A": "left/A.kt"}}, Path("repository"), sources)
        self.assertEqual(mappings, {"example.A": "left/A.kt"})
        self.assertEqual(gaps, [])

    def test_published_dl_arithmetic_and_union_of_reachability(self):
        nodes = {str(n) for n in range(100)}
        for size, expected in ((4, 100), (25, 50), (100, 100 * math.log(5) / math.log(100))):
            groups = [{"layer": 1, "files": [str(n) for n in range(start, start + size)]} for start in range(0, 100, size)]
            self.assertAlmostEqual(decoupling_level(nodes, set(), groups)["value"], expected)
        edges = {("a", "x"), ("a", "y"), ("b", "x")}
        value = decoupling_level(set("abxy"), edges, [{"layer": 1, "files": ["x", "y"]}, {"layer": 2, "files": ["a"]}, {"layer": 2, "files": ["b"]}])
        self.assertEqual(value["groups"][0]["affected_lower_files"], 2)
        self.assertEqual(value["value"], 50)

    def test_hierarchy_partition_layers_recursion_and_isolates(self):
        # Shared supplier regions and a dense controller module exercise separate DRH steps.
        nodes = set("abcdefxyz")
        edges = {("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"), ("e", "d"), ("x", "y"), ("y", "x")}
        groups = hierarchy(nodes, edges)
        self.assertEqual(sorted(n for group in groups for n in group["files"]), sorted(nodes))
        owners = {n: index for index, group in enumerate(groups) for n in group["files"]}
        for left, right in edges:
            if owners[left] != owners[right]:
                self.assertGreater(groups[owners[left]]["layer"], groups[owners[right]]["layer"])
        self.assertEqual(groups, hierarchy(reversed(sorted(nodes)), reversed(sorted(edges))))
        for node in ("f", "z"):
            self.assertIn({"files": [node], "layer": max(row["layer"] for row in groups)}, groups)
        value = structural_metrics(set("abc"), {("a", "b")})
        self.assertEqual(value["propagation_cost"], 4 / 9)
        self.assertEqual(value["largest_scc_size"], 1)
        self.assertEqual(value["visibility_in"]["c"], 1 / 3)
        self.assertEqual(structural_metrics(set(), set())["decoupling_level"]["status"], "not_applicable")

    def test_weighted_cognitive_and_maximum_container_penalty(self):
        files = {"A": file_row("A", count=600, complexity=30)}
        files["A"]["containers"].append({"kind": "class", "start": 0, "end": 1200})
        files["A"]["functions"].append({"start": 2, "end": 10, "nested": True, "cognitive_complexity": 100})
        value = maintainability(files, PARAMETERS)
        self.assertEqual(value["cognitive_score"], 50)
        self.assertEqual(value["size_score"], 50)
        self.assertEqual(value["value"], 50)
        self.assertEqual(value["function_count"], 1)
        self.assertEqual(value["complex_tokens"], 600)
        self.assertEqual(value["weighted_p95_cognitive_complexity"], 30)
        files["A"]["functions"] = []
        self.assertIsNone(maintainability(files, PARAMETERS)["value"])

    def test_exact_clone_union_overlap_and_cross_module_exposure(self):
        files = {path: file_row(path, count=120) for path in ("A", "B")}
        values, boundary = duplication(files, 100, {"A": "left", "B": "right"})
        self.assertEqual(values["A"]["tokens"], 120)
        self.assertEqual(boundary["B"]["tokens"], 120)
        repeated = {"A": file_row("A", count=150, texts=["same"] * 150)}
        self.assertEqual(duplication(repeated, 100, {"A": "left"})[0]["A"]["tokens"], 0)
        repeated["A"] = file_row("A", count=200, texts=["same"] * 200)
        self.assertEqual(duplication(repeated, 100, {"A": "left"})[0]["A"]["tokens"], 200)
        files["B"]["tokens"][50]["text"] = "renamed"
        self.assertEqual(duplication(files, 100, {"A": "left", "B": "right"})[0]["A"]["tokens"], 0)

    def test_method_crap_before_aggregation_and_missing_branch_counter(self):
        sources = {"A.kt": {"package": "example"}}
        methods, lines = coverage_methods(jacoco(), sources, {"example.A": "A.kt"})
        value = coverage_summary({"A.kt"}, methods, lines, 1000)
        self.assertAlmostEqual(value["total_excess"], 2.8)
        self.assertAlmostEqual(value["total_crap"], 16.8)
        self.assertAlmostEqual(value["E_CRAP"], 100 * 2.8 / 116)
        self.assertEqual(value["branch"]["value"], .5)
        self.assertEqual(value["instruction"]["value"], .65)
        self.assertEqual(value["line"]["value"], .5)
        self.assertEqual(lines, {("A.kt", 3): True, ("A.kt", 17): False})
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            coverage_methods(jacoco().replace('<counter type="INSTRUCTION" covered="5" missed="5"/>', ""), sources, {"example.A": "A.kt"})

    def test_coverage_uses_reported_classes_and_lines_within_each_scope(self):
        sources = {path: {"package": "example"} for path in ("A.kt", "B.kt")}
        mappings = {"example.A": "A.kt", "example.Filtered": "A.kt", "example.B": "B.kt"}
        methods, lines = coverage_methods(jacoco(), sources, mappings)
        self.assertEqual(len(methods), 2)
        self.assertEqual(coverage_summary(set(sources), methods, lines, 100)["line"], {
            "value": .5, "numerator": 1, "denominator": 2, "status": "measured_subset", "omitted_files": ["B.kt"]})
        self.assertEqual(coverage_summary({"A.kt"}, methods, lines, 50)["line"]["status"], "known")
        self.assertEqual(coverage_summary({"B.kt"}, methods, lines, 50)["line"]["status"], "unknown")
        self.assertEqual(coverage_summary(set(), methods, lines, 0)["line"]["status"], "not_applicable")

    def test_sourcefile_line_counter_must_match_covered_and_missed_records(self):
        xml = jacoco()
        for invalid in (xml.replace('<line nr="17" ci="0" mi="2"/>', ''),
                        xml.replace('type="LINE" covered="1" missed="1"', 'type="LINE" covered="2" missed="0"')):
            with self.subTest(xml=invalid), self.assertRaisesRegex(ValueError, "LINE counter mismatch for A.kt"):
                coverage_methods(invalid, {"A.kt": {"package": "example"}}, {"example.A": "A.kt"})

    def test_module_scores_recomputed_and_boundary_cycles_remain_visible(self):
        files = {"A": file_row("A", "left", 100), "B": file_row("B", "right", 100)}
        value = indicators(files, {("A", "B"), ("B", "A")}, {"left": ["left"], "right": ["right"]}, [], {}, [], PARAMETERS, date(2026, 11, 15))
        self.assertLess(value["project"]["U"], value["modules"]["left"]["U"])
        self.assertEqual(value["project"]["structure"]["cyclic_files"], 2)
        self.assertEqual(value["modules"]["left"]["boundary"]["outgoing_edges"], 1)
        self.assertEqual(value["modules"]["left"]["boundary"]["cross_module_duplicate_tokens"], 100)
        self.assertAlmostEqual(value["project"]["Q"], (value["project"]["D"] * value["project"]["L"] * value["project"]["U"]) ** (1 / 3))
        with self.assertRaisesRegex(ValueError, "Assign production"):
            indicators(files, set(), {"left": ["left"]}, [], {}, [], PARAMETERS, date(2026, 11, 15))

    def test_kotlin_population_must_be_complete(self):
        source = {"A": {"package": "example", "language": ".kt"}}
        self.assertEqual(set(qualify_kotlin(kotlin([file_row("A")]), source)), {"A"})
        with self.assertRaisesRegex(ValueError, "exactly once"):
            qualify_kotlin(kotlin([]), source)


class PublicationTests(unittest.TestCase):
    def test_full_audit_publication_and_failure_preserve_previous_status(self):
        # Risk: final publication can overwrite live status before all source/report gates.
        # One filesystem scenario verifies the actual filenames and contents; rule variants use mocks.
        with tempfile.TemporaryDirectory(prefix="architect-publication-") as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/A.kt").write_text("package example\nclass A", encoding="utf-8")
            audit = root / "memory/tech-debt/audits/2026-11-15T12-00-00Z"
            raw = audit / "raw"
            raw.mkdir(parents=True)
            text = {
                "dependencies": ("jdeps", ""),
                "complexity": ("detekt-sarif", '{"runs": []}'),
                "coverage": ("jacoco", jacoco(with_lines=False)),
                "history": ("git-history", json.dumps({"format": "git-history", "first_parent": True, "renames": True,
                    "since": (datetime.now(timezone.utc).date() - timedelta(days=PARAMETERS["history_days"])).isoformat(),
                    "until": datetime.now(timezone.utc).date().isoformat(), "commits": []})),
                "sizes": ("scc", json.dumps([{"Name": "Kotlin", "Files": [{"Location": "src/A.kt", "Lines": 2, "Code": 2, "Comment": 0, "Blank": 0}]}])),
                "kotlin": ("kotlin-measurements", json.dumps(kotlin([file_row("src/A.kt")]))),
            }
            config = {"source_roots": ["src"], "package_prefixes": ["example"],
                      "class_files": {"example.A": "src/A.kt", "example.Filtered": "src/A.kt"},
                      "modules": {"example": ["example"]}, "artifacts": {}}
            for name, (format_name, payload) in text.items():
                path = raw / (name + ".input")
                path.write_text(payload, encoding="utf-8")
                config["artifacts"][name] = {"path": path.relative_to(root).as_posix(), "format": format_name, "tool": name, "version": "fixture", "command": [name]}
            config["artifacts"]["coverage"].update(complete=True, test_result="passed")
            status = root / "memory/tech-debt/status.json"
            status.write_text("previous", encoding="utf-8")
            guide = status.with_name("status-indicators.md")
            guide.write_text("previous guide", encoding="utf-8")
            collection = {"command": ["project-task", "audit inputs"], "artifacts": config.pop("artifacts")}
            settings = root / ".sdd/settings.json"
            settings.parent.mkdir()
            def save_settings():
                settings.write_text(json.dumps({"schema_version": 1, "architect": {"collection": collection}}))
            save_settings()
            with patch("collection.run") as execute:
                description = collect(config, audit, repository=root)
            execute.assert_called_once_with(collection["command"], root, POLICY)
            self.assertEqual(description["status"], "complete")
            self.assertEqual(status.read_text(), "previous")
            with self.assertRaisesRegex(ValueError, "Finish the report"):
                publish_status(audit / "collection.json", root)
            self.assertEqual(status.read_text(), "previous")
            self.assertEqual(guide.read_text(), "previous guide")
            (audit / "report.md").write_text("Finished audit", encoding="utf-8")
            plan = root / "memory/tech-debt/plan"
            plan.mkdir()
            (plan / "plan.md").write_text("Finished plan update", encoding="utf-8")
            publish_status(audit / "collection.json", root)
            value = json.loads(status.read_text(encoding="utf-8"))
            self.assertEqual(value["project"]["statistics"]["total"]["Code"], 2)
            for scope in (value["project"], value["modules"]["example"]):
                coverage = scope["coverage"]
                self.assertIsNone(coverage["line"]["value"])
                self.assertEqual(coverage["line"]["status"], "unknown")
                self.assertEqual(coverage["line"]["omitted_files"], ["src/A.kt"])
                self.assertEqual(coverage["instruction"]["value"], .65)
                self.assertEqual(coverage["branch"]["value"], .5)
                self.assertAlmostEqual(coverage["total_crap"], 16.8)
            markdown = status.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("Нет данных", markdown)
            self.assertIn("- src/A.kt", markdown)
            self.assertEqual(markdown, render_status(value))
            bundled = Path(__file__).resolve().parents[1] / "assets" / guide.name
            self.assertEqual(guide.read_bytes(), bundled.read_bytes())
            targets = re.findall(r"\]\(status-indicators\.md#([^)]*)\)", markdown)
            guide_text = guide.read_text(encoding="utf-8")
            headings = re.findall(r"^### (.+)$", guide_text, re.MULTILINE)
            for heading in headings:
                self.assertRegex(heading, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertRegex(guide_text, rf"(?m)^### {heading}\n\n\*\*[^*\n]+\*\*$")
            self.assertTrue(targets)
            self.assertEqual(set(targets), set(headings))
            self.assertEqual(len(headings), len(set(headings)))
            before = status.read_bytes()
            del collection["artifacts"]["coverage"]
            save_settings()
            with self.assertRaisesRegex(ValueError, "sdd-setup.*coverage"):
                collect(config, audit.with_name("2026-11-15T13-00-00Z"), repository=root)
            self.assertEqual(status.read_bytes(), before)
            self.assertEqual(json.loads((audit.with_name("2026-11-15T13-00-00Z") / "collection.json").read_text())["status"], "blocked")
