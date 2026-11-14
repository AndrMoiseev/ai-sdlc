import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis import prepare_measurements, suitability
from collection import collect, report_output
from graph import graph_view, module_for, module_views
from history import group_activity, history_view, parse_history
from inputs import class_source_file, coverage, dependencies, detekt, relative_path, source_description
from metrics import main, write_json
from measurements import CATALOG, ordered_rows, record_key, resolve_reference
from recommendations import markdown, rank, validate_card


def finding(rule, message, line=10):
    return {"ruleId": "detekt.complexity." + rule, "message": {"text": message},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/Price.kt"},
                                                "region": {"startLine": line}}}]}


def card(identity, effect):
    return {"id": identity, "status": "ready", "card": f"recommendations/{identity}.md",
            "metric_evidence": [],
            "source_evidence": [{"file": "src/Price.kt", "declaration": "price(lines: List<Line>): Money"}],
            "effects": dict(zip(("modularity", "regression_risk", "development_speed"), effect))}


def card_markdown(identity):
    return f"""# {identity}: Extract price calculation

## 1. Problem and scenario
A regional rounding rule changes alongside transport handling in Price.

## 2. Evidence
Inspected src/Price.kt, price(lines: List<Line>): Money and its consumer.

## 3. Mechanism
The consumer knows the rounding policy. Source inspection ruled out generated code.

## 4. Direction
Let pricing own the calculation and hide the policy from its consumer.

## 5. Effects and alternatives
Local modularity and risk benefit are predicted; current coupling persists without change.

## 6. Questions for sdd-spec
Choose the API and package layout with a human. Preserve rounding behavior;
a policy change should no longer require changing the transport consumer.
"""


def prepare_memory(payloads, sources=None, mappings=None, config=None):
    artifacts = {name: {"status": "complete", "tool": name, "version": "fixture", "command": [name],
                        "source_root": "/checkout", **spec} for name, (_, spec) in payloads.items()}
    rows, outcomes, selections, gaps = prepare_measurements(
        {"package_prefixes": ["a", "b"], **(config or {})}, sources or {}, mappings or {}, [],
        {name: text for name, (text, _) in payloads.items()}, artifacts)
    return {"rows": rows, "outcomes": outcomes, "selections": selections, "gaps": gaps, "artifacts": artifacts}


class GraphTests(unittest.TestCase):
    def test_published_cycle_and_counterfactual(self):
        edges = {pair: 1 for pair in [("A", "B"), ("B", "C"), ("C", "B"), ("D", "C"), ("E", "D")]}
        before = graph_view(edges)
        self.assertEqual(before["cyclic_components"], [["B", "C"]])
        self.assertEqual(before["propagation_cost"], {"numerator": 14, "denominator": 25, "value": .56})
        del edges["C", "B"]
        after = graph_view(edges)
        self.assertEqual(after["propagation_cost"]["numerator"], 11)
        self.assertEqual(after["cyclic_components"], [])
        self.assertIsNone(graph_view({})["propagation_cost"]["value"])

    def test_weights_are_not_neighbour_counts(self):
        value = graph_view({("a", "b"): 8, ("c", "b"): 4})["nodes"]["b"]
        self.assertEqual(value["fan_in"], 2)
        self.assertEqual(value["incoming_weight"], 12)
        self.assertEqual(value["reachable_in"], 3)

    def test_cohesion_affinity_and_weighted_martin(self):
        modules = {"left": ["a"], "right": ["b"], "empty": ["z"]}
        view = module_views({("a.x", "a.y"): 90, ("a.x", "b.x"): 10}, modules, {"a.x": {"types": 5, "abstract": 1}})
        self.assertEqual(view["cohesion"]["left"]["value"], .9)
        self.assertEqual(view["cohesion"]["right"]["value"], 0)
        self.assertIsNone(view["cohesion"]["empty"]["value"])
        self.assertEqual(view["external_affinity"]["a.x"]["shares"], {"right": 1})
        self.assertEqual(view["martin"]["a.x"]["Ce"], 100)
        self.assertEqual(view["martin"]["a.x"]["A"], .2)

    def test_segment_ownership_and_nested_jvm_identity(self):
        self.assertIsNone(module_for("ab", {"A": ["a"]}))
        self.assertEqual(module_for("a.b.c", {"A": ["a"], "B": ["a.b"]}), "B")
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            module_for("a.b", {"A": ["a"], "B": ["a"]})
        self.assertEqual(dependencies("  a.Foo$Inner -> a.Bar classes\n", "jdeps", ["a"]), {("a.Foo$Inner", "a.Bar"): 1})


class HistoryTests(unittest.TestCase):
    def test_filtered_support_and_symmetric_degree(self):
        commits = []
        for index in range(30):
            paths = ["B.kt", "C.kt"] if index < 10 else ["C.kt"]
            commits.append({"revision": str(index), "date": "2026-01-01", "author": "a",
                            "changes": {path: {"added": 1, "deleted": 2, "binary": False} for path in paths}})
        commits.append({"revision": "mass", "date": "2026-01-02", "author": "a",
                        "changes": {path: {"added": 1, "deleted": 0, "binary": False} for path in ["B.kt", "C.kt"] + [str(i) for i in range(29)]}})
        value = history_view(commits)
        pair = value["coupling"][0]
        self.assertEqual((pair["left_revisions"], pair["right_revisions"], pair["shared"], pair["degree"]), (10, 30, 10, 50))
        self.assertEqual(value["revisions"]["B.kt"], 11)
        self.assertEqual(value["churn"]["B.kt"]["added"] + value["churn"]["B.kt"]["deleted"], 31)

    def test_unique_group_commits_and_inclusive_window(self):
        text = "--abc--2026-01-01--a\n1\t2\tA.kt\n1\t1\tB.kt\n--def--2026-01-31--b\n-\t-\timage.bin\n0\t1\tA.kt\n"
        commits = parse_history(text)
        groups = group_activity(commits, {"A.kt": "one", "B.kt": "one"})
        self.assertEqual(groups["one"], {"commits": 2, "commits_last_30_days": 2, "file_occurrences": 3})
        self.assertEqual(history_view(commits)["churn"]["image.bin"]["binary_changes"], 1)

    def test_ambiguous_rename_is_not_silently_joined(self):
        with self.assertRaisesRegex(ValueError, "no-renames"):
            parse_history("--abc--2026-01-01--a\n1\t1\tsrc/{old => new}/A.kt\n")
        parsed = parse_history("--abc--2026-01-01--a\n1\t1\tsrc/Percent%20.kt\n")
        self.assertIn("src/Percent%20.kt", parsed[0]["changes"])
        for path in ("../outside.kt", "/outside.kt", "C:/outside.kt"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "repository-relative"):
                parse_history(f"--abc--2026-01-01--a\n1\t1\t{path}\n")


class AdapterTests(unittest.TestCase):
    def test_detekt_measured_values_not_threshold_or_warning_count(self):
        rows = [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12). threshold 1"),
                finding("LongParameterList", "The f(a: Pair<A,B>, b: (A,B)->C) threshold is 1."),
                finding("LongMethod", "function is too long (21). maximum 1"),
                finding("TooManyFunctions", "Class 'Price' with '11' functions detected. threshold 1")]
        parsed = detekt(json.dumps({"runs": [{"results": rows + [rows[0]]}]}), "/checkout")
        self.assertEqual([row["value"] for row in parsed], [12, None, 21, 11])
        self.assertEqual(parsed[0]["record"], "complexity:runs/0/results/0")

    def test_coverage_missing_zero_and_ambiguous_mapping(self):
        sources = {"src/Price.kt": {"package": "a"}}
        xml = '<report><package name="a"><sourcefile name="Price.kt"><counter type="LINE" covered="0" missed="5"/><counter type="BRANCH" covered="0" missed="0"/></sourcefile></package></report>'
        rows, gaps = coverage(xml, "jacoco", "/checkout", sources)
        self.assertEqual(rows["src/Price.kt"]["line"]["value"], 0)
        self.assertIsNone(rows["src/Price.kt"]["branch"]["value"])
        sources["other/Price.kt"] = {"package": "a"}
        rows, gaps = coverage(xml, "jacoco", "/checkout", sources)
        self.assertEqual(rows, {})
        self.assertEqual(len(gaps[0]["matches"]), 2)

    def test_duplicate_coverage_and_invalid_counters_fail(self):
        text = "file,line_covered,line_total,branch_covered,branch_total\nsrc/A.kt,2,1,0,0\n"
        with self.assertRaisesRegex(ValueError, "Invalid coverage"):
            coverage(text, "coverage-csv", "/checkout", {})
        valid = text.replace(",2,1,", ",1,1,")
        with self.assertRaisesRegex(ValueError, "Duplicate coverage"):
            coverage(valid + valid.splitlines()[1] + "\n", "coverage-csv", "/checkout", {})

    def test_uri_mapping_is_not_basename_matching(self):
        self.assertEqual(relative_path("file:///C:/work/src/My%20File.kt", "C:/work"), "src/My File.kt")
        with self.assertRaisesRegex(ValueError, "Unmapped"):
            relative_path("file:///other/src/My.kt", "/checkout")
        with self.assertRaises(ValueError):
            relative_path("../secret.kt", "/checkout")

    def test_sourcefile_attribute_maps_custom_facade(self):
        def utf8(value):
            encoded = value.encode()
            return b"\x01" + struct.pack(">H", len(encoded)) + encoded
        pool = utf8("a/CustomFacade") + b"\x07\x00\x01" + utf8("SourceFile") + utf8("Price.kt")
        data = b"\xca\xfe\xba\xbe\x00\x00\x00\x3d\x00\x05" + pool
        data += struct.pack(">HHHHHHH", 0x21, 2, 0, 0, 0, 0, 1) + struct.pack(">HIH", 3, 2, 4)
        self.assertEqual(class_source_file(data), ("a.CustomFacade", "Price.kt"))

    def test_source_counts_remain_explicit_heuristic(self):
        value = source_description('package a\n// interface Fake\ndata class X(val s: String)\ninterface API\nsealed class S\nabstract class A', ".kt")
        self.assertEqual((value["types"], value["abstract"]), (4, 2))
        self.assertIsNone(source_description("package a; class JavaType {}", ".java")["types"])


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"src/Price.kt": {}}
        self.document = {"recommendations": []}

    def rank(self, sources=None, resolve_metric=None):
        return rank(self.document, self.sources if sources is None else sources, resolve_metric,
                    lambda path: card_markdown(Path(path).stem))

    def test_modularity_precedes_large_risk_improvement_and_ties_remain(self):
        self.document["recommendations"] = [card("R", ("not_shown", "substantial", "local")),
                                             card("M", ("local", "local", "not_shown")),
                                             card("T", ("local", "local", "not_shown"))]
        self.assertEqual(self.rank()["priority_groups"], [["M", "T"], ["R"]])

    def test_direction_with_open_design_questions_is_ready_and_links_its_card(self):
        self.document["recommendations"] = [card("R1", ("local", "local", "not_shown"))]
        value = self.rank()
        self.assertEqual(value["priority_groups"], [["R1"]])
        self.assertNotIn("execution_order", value)
        rendered = markdown(value)
        self.assertIn("[R1: Extract price calculation](<recommendations/R1.md>)", rendered)
        self.assertNotIn("implementation-ready", rendered)
        self.assertNotIn("Choose the API", json.dumps(value))

    def test_ready_rejects_missing_sources_and_unresolved_effects(self):
        self.document["recommendations"] = [card("M", ("local", "local", "not_shown"))]
        with self.assertRaisesRegex(ValueError, "inspected sources"):
            self.rank(sources={})
        for effect in ("unknown", "worsening"):
            self.document["recommendations"][0]["effects"]["modularity"] = effect
            with self.subTest(effect=effect), self.assertRaisesRegex(ValueError, "cannot be ready"):
                self.rank()
        self.document["recommendations"][0]["status"] = "needs_check"
        self.assertEqual(self.rank()["priority_groups"], [])

    def test_narrative_and_design_stay_out_of_ranking_metadata(self):
        value = card("M", ("local", "local", "not_shown"))
        value["steps"] = ["Design the API", "Implement it"]
        self.document["recommendations"] = [value]
        with self.assertRaisesRegex(ValueError, "Markdown card, not ranking metadata"):
            self.rank()

    def test_six_sections_are_ordered_nonempty_and_not_faked_inside_a_diagram(self):
        text = card_markdown("R1")
        diagram = "```mermaid\nflowchart LR\n  current --> proposed\n```\n"
        self.assertEqual(validate_card(text.replace("Let pricing", diagram + "Let pricing")),
                         "R1: Extract price calculation")
        invalid = [text.replace("## 3.", "## 2."), text.replace("## 6.", "### 6."),
                   text.split("## 6.")[0] + "## 6. Questions\n",
                   "# R1\n```markdown\n" + text + "\n```\n"]
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_card(content)

    def test_invalid_or_duplicate_card_addresses_are_rejected(self):
        value = card("R1", ("local", "local", "not_shown"))
        self.document["recommendations"] = [value]
        for path in ("../outside.md", "/outside.md", "C:/outside.md", "cards.json"):
            value["card"] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "relative Markdown"):
                self.rank()
        value["card"] = "recommendations/R1.md"
        duplicate = {**value, "id": "R2"}
        self.document["recommendations"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "own Markdown card"):
            self.rank()

    def test_ready_without_source_version_and_metric_reference_validation(self):
        value = card("M", ("local", "local", "not_shown"))
        self.document["recommendations"] = [value]
        self.assertEqual(self.rank()["priority_groups"], [["M"]])
        value["metric_evidence"] = [{"path": "metrics/line-coverage/file.jsonl", "key": {"file": "src/Price.kt"}}]
        with self.assertRaisesRegex(ValueError, "metric evidence"):
            self.rank()
        seen = []
        self.rank(resolve_metric=seen.append)
        self.assertEqual(seen, value["metric_evidence"])
        self.assertEqual(suitability({"status": "complete", "tool": "detekt", "version": "test", "command": ["detekt"]}), "usable")


class ReportOutputTests(unittest.TestCase):
    def test_outputs_require_a_named_project_report_directory(self):
        repo = Path(tempfile.gettempdir()) / "architect-project"
        report = repo / "docs" / "reports" / "pricing-audit"
        with patch.object(Path, "resolve", lambda path: path):
            self.assertEqual(report_output(report / "metrics", repo), report / "metrics")
            self.assertEqual(report_output(report / "report.md", repo), report / "report.md")
            for path in (repo / "report.md", repo.parent / "report.md",
                         repo / "docs" / "reports", repo / "docs" / "reports" / "report.md"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "docs/reports"):
                    report_output(path, repo)
            with self.assertRaisesRegex(ValueError, "repository is required"):
                report_output(report / "report.md", None)
            with self.assertRaisesRegex(ValueError, "skill collections"):
                report_output(repo / ".agents" / "skills" / "audit" / "report.md", repo)

    def test_resolved_output_cannot_escape_reports(self):
        repo = Path(tempfile.gettempdir()) / "architect-project"
        output = repo / "docs" / "reports" / "pricing-audit" / "report.md"
        # Model a symlink resolution through the existing Path adapter; no real link is needed.
        with patch.object(Path, "resolve", lambda path: repo.parent / "report.md" if path == output else path):
            with self.assertRaisesRegex(ValueError, "docs/reports"):
                report_output(output, repo)

class CollectionIntegrationTests(unittest.TestCase):
    def test_collect_jsonl_and_rank_current_sources(self):
        # Risk: CLI, physical JSONL files, raw retention and keyed reads can disagree.
        # This extends the existing filesystem integration; pure adapters cannot verify writes.
        with tempfile.TemporaryDirectory(prefix="sdd-architect-test-") as temporary:
            workspace = Path(temporary)
            repo = workspace / "project"
            (repo / "src").mkdir(parents=True)
            (repo / "src" / "Price.kt").write_text("package a\nclass Price", encoding="utf-8")
            report = repo / "docs" / "reports" / "pricing-audit"
            raw = report / "raw"
            raw.mkdir(parents=True)
            (raw / "detekt.sarif").write_text(json.dumps({"runs": [{"results": [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)")]}]}), encoding="utf-8")
            (raw / "coverage.csv").write_text("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,2,10,0,0\n", encoding="utf-8")
            config = {"repository": str(repo), "source_roots": ["src"], "modules": {"A": ["a"]},
                      "artifacts": {"complexity": {"path": str(raw / "detekt.sarif"), "format": "detekt-sarif", "complete_mcc": True},
                                    "coverage": {"path": str(raw / "coverage.csv"), "format": "coverage-csv"}}}
            config_path = workspace / "collection-input.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with patch("collection.run", side_effect=AssertionError("Git or another command was unexpectedly invoked")), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(["collect", "--config", str(config_path), "--output", str(report)]), 0)
            description = json.loads((report / "collection.json").read_text(encoding="utf-8"))
            self.assertEqual(set(description["outputs"]), set(CATALOG))
            self.assertEqual(description["status"], "complete")
            self.assertEqual(description["parameters"]["candidate_group_limit"], 12)
            self.assertEqual(set(description["selections"]), {"rankings", "signals", "candidate-groups", "investigation-queue"})
            groups = [json.loads(line) for line in (report / "selections/candidate-groups.jsonl").read_text(encoding="utf-8").splitlines()]
            queue = [json.loads(line) for line in (report / "selections/investigation-queue.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(groups[0]["scope"]["files"], ["src/Price.kt"])
            self.assertEqual(queue[0]["candidate_group"]["key"]["group"], groups[0]["group"])
            self.assertTrue(queue[0]["selected"])
            self.assertEqual(len(list(raw.iterdir())), 2)
            for name, spec in CATALOG.items():
                content = (report / spec["path"]).read_text(encoding="utf-8")
                rows = [json.loads(line) for line in content.splitlines() if line.strip()]
                self.assertTrue(all(isinstance(row, dict) for row in rows))
                self.assertEqual(rows, ordered_rows(name, rows))
                self.assertEqual(len(rows), description["outputs"][name]["records"])
            ref = {"path": "metrics/crap-file/file.jsonl", "key": {"file": "src/Price.kt"}}
            self.assertAlmostEqual(resolve_reference(ref, description, report)["value"], 85.728)
            self.assertEqual(resolve_reference({"path": "metrics/branch-coverage/file.jsonl", "key": ref["key"]}, description, report)["status"], "not_applicable")
            for selection in description["selections"].values():
                for line in (report / selection["path"]).read_text(encoding="utf-8").splitlines():
                    row = json.loads(line)
                    for link in row.get("references", [row] if "path" in row else []):
                        resolve_reference(link, description, report)
            # A new current file is eligible even though it was absent during collection.
            (repo / "src" / "Price.kt").write_text("package a\nclass Price { fun price() = 1 }", encoding="utf-8")
            (repo / "src" / "Consumer.kt").write_text("package a\nclass Consumer", encoding="utf-8")
            ready = card("R1", ("local", "local", "not_shown"))
            ready["source_evidence"].append({"file": "src/Consumer.kt", "declaration": "Consumer"})
            ready["metric_evidence"] = [ref]
            (report / "recommendations").mkdir()
            (report / ready["card"]).write_text(card_markdown("R1"), encoding="utf-8")
            write_json(report / "cards.json", {"recommendations": [ready]}, repo)
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(["rank", "--collection", str(report / "collection.json"),
                                       "--recommendations", str(report / "cards.json"), "--output", str(report / "ranked.json"),
                                       "--markdown", str(report / "ranked.md")]), 0)
            self.assertIn("Extract price calculation", (report / "ranked.md").read_text(encoding="utf-8"))
            self.assertIn("recommendations/R1.md", (report / "ranked.md").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((report / "ranked.json").read_text(encoding="utf-8"))["priority_groups"], [["R1"]])
            self.assertNotIn("source_files", description)
            for field in ("revision", "dirty", "source_state", "sha256"):
                self.assertNotIn(field, json.dumps(description))
            self.assertFalse(list(report.glob("snapshot*")))
            self.assertFalse(list(report.glob("analysis-*.json")))
            with self.assertRaisesRegex(ValueError, "already exists"):
                collect(config, report)
            with self.assertRaisesRegex(ValueError, "already exists"):
                write_json(report / "cards.json", {}, repo)
            for invalid in ({"path": "../escape.jsonl", "key": {}}, {**ref, "key": {"file": "absent.kt"}}):
                with self.assertRaises(ValueError):
                    resolve_reference(invalid, description, report)


class MeasurementTests(unittest.TestCase):
    def test_interrupted_collection_records_unfinished_outputs(self):
        root = Path(tempfile.gettempdir()) / "architect-project"
        report = root / "docs" / "reports" / "audit"
        saved = []
        with (patch.object(Path, "resolve", lambda path: path), patch.object(Path, "is_dir", return_value=True),
              patch.object(Path, "exists", return_value=False), patch.object(Path, "mkdir"),
              patch.object(Path, "write_text", lambda path, text, **kwargs: saved.append(json.loads(text))),
              patch("collection.inventory", side_effect=KeyboardInterrupt("Source read interrupted"))):
            with self.assertRaisesRegex(KeyboardInterrupt, "interrupted"):
                collect({"repository": str(root)}, report)
        self.assertEqual(saved[0]["status"], "incomplete")
        self.assertTrue(all(row["status"] == "incomplete" for row in saved[0]["outputs"].values()))
        self.assertTrue(all(row["status"] == "incomplete" for row in saved[0]["selections"].values()))

    def test_git_failure_only_limits_requested_history_chain(self):
        root = Path(tempfile.gettempdir()) / "architect-project"
        report = root / "docs" / "reports" / "audit"
        config = {"repository": str(root), "artifacts": {
            "history": {"collect": True}, "coverage": {"path": str(root / "coverage.csv"), "format": "coverage-csv"}}}
        with (patch.object(Path, "resolve", lambda path: path), patch.object(Path, "is_dir", return_value=True),
              patch.object(Path, "exists", return_value=False), patch.object(Path, "mkdir"),
              patch.object(Path, "write_text"), patch.object(Path, "write_bytes"),
              patch.object(Path, "read_bytes", return_value=b"file,line_covered,line_total,branch_covered,branch_total\nsrc/A.kt,0,2,0,0\n"),
              patch("collection.inventory", side_effect=OSError("Source read unavailable")), patch("collection.map_classes", return_value=({}, [])),
              patch("collection.write_jsonl"), patch("collection.run", side_effect=FileNotFoundError("Git unavailable")) as command):
            value = collect(config, report)
        self.assertEqual(value["status"], "complete")
        self.assertEqual(value["outputs"]["changes/commit"]["status"], "error")
        self.assertEqual(value["outputs"]["source-files/file"]["status"], "error")
        self.assertEqual(value["outputs"]["line-coverage/file"]["status"], "complete")
        self.assertEqual(command.call_count, 1)
        self.assertIn("log", command.call_args.args[0])
        self.assertNotIn("HEAD", command.call_args.args[0])

    def test_missing_mcc_and_partial_coverage_remain_visible(self):
        findings = [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)"),
                    finding("CyclomaticComplexMethod", "Changed instrument message; threshold 1", 20)]
        sources = {"src/Price.kt": {"package": "a", "types": 1, "abstract": 0},
                   "src/Missing.kt": {"package": "a", "types": 1, "abstract": 0}}
        value = prepare_memory({
            "complexity": (json.dumps({"runs": [{"results": findings}]}), {"complete_mcc": True}),
            "coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,2,10,0,0\n", {"format": "coverage-csv"})}, sources)
        rows = value["rows"]
        mcc = {row["file"]: row for row in rows["cyclomatic-complexity/file"]}
        self.assertFalse(mcc["src/Price.kt"]["population_complete"])
        self.assertIsNone(mcc["src/Missing.kt"]["value"])
        self.assertEqual(rows["line-coverage/package"][0]["status"], "measured_subset")
        self.assertEqual(rows["line-coverage/package"][0]["omitted_files"], ["src/Missing.kt"])
        self.assertEqual(rows["branch-coverage/package"][0]["status"], "unknown")
        self.assertEqual(rows["crap-sum/package"][0]["incomplete_files"], ["src/Price.kt"])
        self.assertEqual(next(row for row in value["selections"]["signals"] if row["family"] == "crap")["weights_MRS"], [0, 1, 0])

    def test_empty_unavailable_error_and_zero_are_distinct(self):
        empty = prepare_memory({"dependencies": ("from,to\n", {"format": "class-csv"}),
                                "complexity": ('{"runs":[]}', {})})
        self.assertEqual(empty["outcomes"]["dependencies/class"]["status"], "complete")
        self.assertEqual(empty["rows"]["dependencies/class"], [])
        self.assertEqual(empty["rows"]["node-count/class"][0]["value"], 0)
        self.assertEqual(empty["rows"]["propagation-cost/class"][0]["status"], "not_applicable")
        self.assertEqual(empty["outcomes"]["line-coverage/file"]["status"], "unavailable")
        broken = prepare_memory({"coverage": ("<broken", {"format": "jacoco"}),
                                 "dependencies": ("from,to\na.A,b.B\n", {"format": "class-csv"})})
        self.assertEqual(broken["outcomes"]["line-coverage/file"]["status"], "error")
        self.assertEqual(broken["rows"]["edge-count/class"][0]["value"], 1)
        malformed = prepare_memory({"complexity": ("[]", {}), "history": ("", {})})
        self.assertEqual(malformed["outcomes"]["cyclomatic-complexity/function"]["status"], "error")
        self.assertEqual(malformed["outcomes"]["changes/commit"]["status"], "complete")
        unmeasured_types = prepare_memory({"dependencies": ("from,to\na.JavaType,b.B\n", {"format": "class-csv"})},
                                         {"src/JavaType.java": {"package": "a", "types": None, "abstract": None}})
        self.assertEqual(unmeasured_types["rows"]["abstractness/package"][0]["status"], "unknown")
        self.assertEqual(unmeasured_types["rows"]["changes-per-code/file"][0]["status"], "not_applicable")

    def test_granularities_weights_support_and_determinism(self):
        history = "".join(f"--{i:x}--2026-01-01--a\n1\t2\tsrc/A.kt\n1\t0\tsrc/B.kt\n" for i in range(5))
        sources = {"src/A.kt": {"package": "a", "types": 5, "abstract": 1},
                   "src/B.kt": {"package": "b", "types": 5, "abstract": 0}}
        mappings = {"a.A": "src/A.kt", "a.A$Inner": "src/A.kt", "b.B": "src/B.kt"}
        payloads = {"history": (history, {}), "dependencies": ("from,to\na.A,b.B\na.A$Inner,b.B\na.A,b.B\n", {"format": "class-csv"}),
                    "coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/A.kt,1,10,1,2\nsrc/B.kt,9,90,2,8\n", {"format": "coverage-csv"})}
        config = {"modules": {"all": ["a", "b"]}}
        first = prepare_memory(payloads, sources, mappings, config)
        second = prepare_memory(dict(reversed(list(payloads.items()))), dict(reversed(list(sources.items()))), mappings, config)
        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(first["selections"], second["selections"])
        rows = first["rows"]
        self.assertEqual(rows["dependencies/package"][0]["value"], 2)
        self.assertEqual(rows["dependencies/module"], [])
        self.assertEqual(rows["node-count/class"][0]["value"], 3)
        self.assertEqual(rows["node-count/package"][0]["value"], 2)
        self.assertEqual(rows["node-count/module"][0]["value"], 0)
        self.assertEqual(rows["coupling/file-pair"][0]["left_frequency"], 5)
        self.assertEqual(rows["coupling/file-pair"][0]["shared"], 5)
        self.assertEqual(rows["activity/module"][0]["value"], 5)
        self.assertEqual(rows["change-frequency/module"][0]["value"], 10)
        self.assertEqual(rows["churn/module"][0]["value"], 20)
        self.assertEqual(rows["line-coverage/module"][0]["value"], .1)
        self.assertEqual(rows["branch-coverage/module"][0]["value"], .3)
        self.assertEqual(rows["hotspot-in-frequency/file"][1]["value"], 5)
        self.assertEqual(rows["implicit-coupling/file-pair"], [])
        for selection in first["selections"].values():
            for row in selection:
                self.assertNotIn("value", row)
                for ref in row.get("references", [row] if "path" in row else []):
                    identifier = next(name for name, spec in CATALOG.items() if spec["path"] == ref["path"])
                    self.assertEqual(sum(record_key(identifier, r) == ref["key"] for r in rows[identifier]), 1)

    def test_coupling_keeps_values_below_threshold_and_mapping_limits(self):
        text = "--a--2026-01-01--a\n1\t0\tsrc/A.kt\n1\t0\tsrc/B.kt\n"
        sources = {"src/A.kt": {"package": "a", "types": 1, "abstract": 0},
                   "src/B.kt": {"package": "b", "types": 1, "abstract": 0}}
        value = prepare_memory({"history": (text, {}), "dependencies": ("from,to\na.A,b.B\n", {"format": "class-csv"})}, sources)
        self.assertEqual(value["rows"]["coupling/file-pair"][0]["shared"], 1)
        self.assertEqual(value["rows"]["implicit-coupling/file-pair"][0]["status"], "measured_subset")
        self.assertFalse(any(s["family"] == "coupling" for s in value["selections"]["signals"]))

    def test_catalog_keys_and_observed_function_population(self):
        findings = [finding("LongParameterList", "f(a: Pair<A,B>) exceeds threshold"),
                    finding("TooManyFunctions", "Object 'X' with '12' functions", 20)]
        findings[1]["suppressions"] = [{"kind": "inSource"}]
        value = prepare_memory({"complexity": (json.dumps({"runs": [{"results": findings}]}), {})})
        parameter = value["rows"]["parameter-list/declaration"][0]
        self.assertIsNone(parameter["value"])
        self.assertEqual(parameter["region"], {"startLine": 10})
        self.assertEqual(value["rows"]["function-count/declaration"][0]["value"], 12)
        self.assertEqual(len(value["selections"]["signals"]), 1)
        self.assertEqual(value["selections"]["signals"][0]["references"][0]["path"], "metrics/parameter-list/declaration.jsonl")
        self.assertEqual(len({spec["path"] for spec in CATALOG.values()}), len(CATALOG))
        for identifier, spec in CATALOG.items():
            self.assertTrue(all(spec[field] for field in ("key", "unit", "kind", "inputs", "meaning")), identifier)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            ordered_rows("code-lines/file", [{"file": "a", "value": 1}, {"file": "a", "value": 2}])

    def test_cli_has_only_collection_and_ranking(self):
        for removed in ("identity", "analyze"):
            with self.subTest(command=removed), patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                main([removed])
