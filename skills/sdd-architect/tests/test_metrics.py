import copy
import io
import json
import struct
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from analysis import analyze, suitability
from collection import collect, digest, report_output
from graph import graph_view, module_for, module_views
from history import group_activity, history_view, parse_history
from inputs import class_source_file, coverage, dependencies, detekt, relative_path, source_description
from metrics import main, write_json
from recommendations import rank


def finding(rule, message, line=10):
    return {"ruleId": "detekt.complexity." + rule, "message": {"text": message},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/Price.kt"},
                                                "region": {"startLine": line}}}]}


def card(identity, effect):
    return {"id": identity, "status": "ready", "cause": identity,
            "action": "Extract price calculation", "scenario": "Change a rounding rule", "mechanism": "I/O mixes with calculation",
            "alternative_explanation": "Checked that calculation has a separate policy owner", "chosen_option": "Pure calculation",
            "baseline": "Mixed function", "expected_effect": "Rule change becomes local", "steps": ["Extract", "Run tests"],
            "cost_and_risk": "One function and its caller; preserve rounding", "acceptance": "Rounding behavior retained",
            "revisit": "Pricing contract changes", "priority_reason": "More independent rule changes",
            "feasible": True, "preserves_required_behavior": True, "boundary_change": False,
            "metric_evidence": [],
            "confidence": {"observation": "high: inspected", "diagnosis": "medium: scenario", "effect": "medium: predicted"},
            "source_evidence": [{"file": "src/Price.kt", "declaration": "price(lines: List<Line>): Money", "finding": "Calculation calls transport"}],
            "effects": dict(zip(("modularity", "regression_risk", "development_speed"), effect)), "depends_on": []}


def analyze_memory(payloads, extra=None):
    directory = Path(tempfile.gettempdir()) / "sdd-architect-memory"
    snapshot = {"revision": "abc", "source_state": "hash", "source_files": {}, "package_prefixes": ["a", "b"],
                "artifacts": {name: {"path": name + ".raw", "sha256": digest(text.encode()), "revision": "abc",
                                     "source_state": "hash", "tool": name, "version": "fixture", "command": [name],
                                     "source_root": "/checkout", **spec}
                              for name, (text, spec) in payloads.items()}, **(extra or {})}
    with patch.object(Path, "read_bytes", lambda path: payloads[path.stem][0].encode()):
        return analyze(snapshot, directory)


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


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"revision": "abc", "source_state": "hash", "source_files": {"src/Price.kt": {}}}
        self.document = {"revision": "abc", "source_state": "hash", "recommendations": []}

    def test_modularity_precedes_large_risk_improvement_and_ties_remain(self):
        self.document["recommendations"] = [card("R", ("not_shown", "substantial", "local")),
                                             card("M", ("local", "local", "not_shown")),
                                             card("T", ("local", "local", "not_shown"))]
        self.assertEqual(rank(self.document, self.snapshot)["priority_groups"], [["M", "T"], ["R"]])

    def test_dependencies_order_execution_not_benefits(self):
        parent, prep = card("M", ("substantial", "local", "not_shown")), card("R", ("not_shown", "local", "not_shown"))
        parent["depends_on"] = ["R"]
        self.document["recommendations"] = [parent, prep]
        value = rank(self.document, self.snapshot)
        self.assertEqual(value["priority_groups"], [["M"], ["R"]])
        self.assertEqual(value["execution_order"], ["R", "M"])
        prep["depends_on"] = ["M"]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            rank(self.document, self.snapshot)

    def test_ready_rejects_source_free_unknown_and_duplicate_cause(self):
        self.document["recommendations"] = [card("M", ("local", "local", "not_shown"))]
        with self.assertRaisesRegex(ValueError, "inspected sources"):
            rank(self.document, {**self.snapshot, "source_files": {}})
        self.document["recommendations"][0]["effects"]["modularity"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown"):
            rank(self.document, self.snapshot)
        first, second = card("A", ("local", "local", "not_shown")), card("B", ("local", "local", "not_shown"))
        second["cause"] = first["cause"]
        self.document["recommendations"] = [first, second]
        with self.assertRaisesRegex(ValueError, "duplicates cause"):
            rank(self.document, self.snapshot)

    def test_boundary_acceptance_is_required(self):
        value = card("M", ("local", "local", "not_shown"))
        value["boundary_change"] = True
        self.document["recommendations"] = [value]
        with self.assertRaisesRegex(ValueError, "ArchUnit"):
            rank(self.document, self.snapshot)

    def test_omitted_boundary_decision_cannot_bypass_validation(self):
        value = card("M", ("local", "local", "not_shown"))
        del value["boundary_change"]
        self.document["recommendations"] = [value]
        with self.assertRaisesRegex(ValueError, "explicit boundary_change"):
            rank(self.document, self.snapshot)

    def test_unknown_revision_is_not_current_because_imported_today(self):
        self.assertEqual(suitability(self.snapshot, {"revision": None})[0], "limited")
        self.assertEqual(suitability(self.snapshot, {"revision": "old", "source_state": "hash"})[0], "unusable")


class ReportOutputTests(unittest.TestCase):
    def test_outputs_require_a_named_project_report_directory(self):
        repo = Path(tempfile.gettempdir()) / "architect-project"
        report = repo / "docs" / "reports" / "pricing-audit"
        with patch.object(Path, "resolve", lambda path: path):
            self.assertEqual(report_output(report / "snapshot-1", repo), report / "snapshot-1")
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

    def test_collection_still_rejects_revision_or_source_changes(self):
        repo = Path(tempfile.gettempdir()) / "architect-project"
        before = {"revision": "abc", "source_state": "original", "dirty": False, "source_files": {}}
        for key in ("revision", "source_state"):
            after = {**before, key: "changed"}
            with self.subTest(key=key), patch.object(Path, "resolve", lambda path: path), \
                    patch.object(Path, "is_dir", return_value=True), \
                    patch.object(Path, "exists", return_value=False), patch.object(Path, "mkdir"), \
                    patch("collection.identity", side_effect=[before, after]), \
                    patch("collection.map_classes", return_value=({}, [])):
                with self.assertRaisesRegex(ValueError, "Source state changed"):
                    collect({"repository": str(repo)}, repo / "docs" / "reports" / "audit" / "snapshot-1")


class SnapshotIntegrationTests(unittest.TestCase):
    def test_collect_analyze_and_raw_tamper(self):
        # Risk: collection, CLI output paths and immutable copies can disagree on actual disk writes.
        # Extend the existing filesystem fixture; in-memory graph/parser tests cannot verify retained files.
        with tempfile.TemporaryDirectory(prefix="sdd-architect-test-") as temporary:
            workspace = Path(temporary)
            repo, raw = workspace / "project", workspace / "reports"
            (repo / "src").mkdir(parents=True)
            raw.mkdir()
            (repo / "src" / "Price.kt").write_text("package a\nclass Price", encoding="utf-8")
            complexity = {"runs": [{"results": [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)")]}]}
            (raw / "detekt.json").write_text(json.dumps(complexity), encoding="utf-8")
            (raw / "coverage.csv").write_text("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,2,10,0,0\n", encoding="utf-8")
            config = {"repository": str(repo), "source_roots": ["src"], "modules": {"A": ["a"]},
                      "artifacts": {"complexity": {"path": str(raw / "detekt.json"), "format": "detekt-sarif", "complete_mcc": True},
                                    "coverage": {"path": str(raw / "coverage.csv"), "format": "coverage-csv"}}}
            report = repo / "docs" / "reports" / "pricing-audit"
            snapshot_dir = report / "snapshot-1"
            with patch("collection.shutil.which", return_value="git"), \
                    patch("collection.run", side_effect=[b"abc", b"", b"abc", b"?? docs/reports/\n"]):
                snapshot = collect(config, snapshot_dir)
            self.assertFalse(snapshot["dirty"])
            self.assertEqual(snapshot["configuration"], config)
            value = analyze(snapshot, snapshot_dir)
            self.assertAlmostEqual(value["files"]["src/Price.kt"]["CRAP_file"], 85.728)
            self.assertEqual(value["files"]["src/Price.kt"]["revisions"], None)
            self.assertEqual(value["signals"][0]["weights_MRS"], [1, 1, 1])
            self.assertEqual(value["aggregates"]["package"]["a"]["coverage"]["line"]["value"], .2)
            snapshot_path = snapshot_dir / "snapshot.json"
            cards = {"revision": snapshot["revision"], "source_state": snapshot["source_state"],
                     "recommendations": [card("R1", ("local", "local", "not_shown"))]}
            write_json(report / "cards.json", cards, repo)
            with patch("builtins.print"):
                self.assertEqual(main(["analyze", "--snapshot", str(snapshot_path),
                                       "--output", str(report / "analysis-1.json")]), 0)
                self.assertEqual(main(["rank", "--snapshot", str(snapshot_path),
                                       "--recommendations", str(report / "cards.json"),
                                       "--output", str(report / "ranked-1.json"),
                                       "--markdown", str(report / "report.md")]), 0)
            self.assertEqual(json.loads((report / "analysis-1.json").read_text(encoding="utf-8")), value)
            self.assertEqual(json.loads((report / "ranked-1.json").read_text(encoding="utf-8"))["priority_groups"], [["R1"]])
            self.assertIn("Extract price calculation", (report / "report.md").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "already exists"):
                collect(config, snapshot_dir)
            with self.assertRaisesRegex(ValueError, "already exists"):
                write_json(report / "cards.json", {}, repo)
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(["analyze", "--snapshot", str(snapshot_path),
                                       "--output", str(repo / "misplaced.json")]), 2)
            self.assertFalse((repo / "misplaced.json").exists())
            (snapshot_dir / "coverage.raw").write_text("tampered", encoding="utf-8")
            altered = analyze(snapshot, snapshot_dir)
            self.assertIsNone(altered["files"]["src/Price.kt"]["CRAP_file"])
            self.assertEqual(altered["artifact_status"]["coverage"]["status"], "unusable")


class IncompleteEvidenceTests(unittest.TestCase):
    def test_unknown_mcc_cannot_claim_complete_crap(self):
        findings = [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)"),
                    finding("CyclomaticComplexMethod", "Changed instrument message; threshold 1", 20)]
        value = analyze_memory({
            "complexity": (json.dumps({"runs": [{"results": findings}]}), {"complete_mcc": True}),
            "coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,2,10,0,0\n", {"format": "coverage-csv"})})
        self.assertFalse(value["files"]["src/Price.kt"]["mcc_population_complete"])
        self.assertEqual(next(s for s in value["signals"] if s["family"] == "crap")["weights_MRS"], [0, 1, 0])

    def test_coverage_membership_and_local_xml_failure(self):
        sources = {"src/Price.kt": {"package": "a", "types": 1, "abstract": 0},
                   "src/Missing.kt": {"package": "a", "types": 1, "abstract": 0}}
        value = analyze_memory({"coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,100,100,0,0\n",
                                               {"format": "coverage-csv"})}, {"source_files": sources})
        counter = value["aggregates"]["package"]["a"]["coverage"]["line"]
        self.assertEqual(counter["status"], "measured_subset")
        self.assertEqual(counter["omitted_files"], ["src/Missing.kt"])
        zero = analyze_memory({"coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,0,0,0,0\n",
                                             {"format": "coverage-csv"})}, {"source_files": sources})
        self.assertEqual(zero["aggregates"]["package"]["a"]["coverage"]["line"]["status"], "unknown")
        broken = analyze_memory({"coverage": ("<broken", {"format": "jacoco"}),
                                 "dependencies": ("from,to\na.A,b.B\n", {"format": "class-csv"})})
        self.assertEqual(broken["artifact_status"]["coverage"]["status"], "unusable")
        self.assertEqual(broken["graphs"]["class"]["edge_count"], 1)

    def test_mapping_limits_absence_separately_from_cochange(self):
        text = "".join(f"--{i:x}--2026-01-01--a\n1\t0\tsrc/A.kt\n1\t0\tsrc/B.kt\n" for i in range(5))
        sources = {"src/A.kt": {"package": "a", "types": 1, "abstract": 0},
                   "src/B.kt": {"package": "b", "types": 1, "abstract": 0}}
        value = analyze_memory({"history": (text, {}), "dependencies": ("from,to\na.A,b.B\n", {"format": "class-csv"})},
                               {"source_files": sources})
        self.assertEqual(value["history"]["coupling"][0]["static_absence_suitability"], "limited")
        self.assertEqual(next(s for s in value["signals"] if s["family"] == "coupling")["weights_MRS"], [2, 1, 1])
        self.assertNotIn("no_direct_static_edge_observed", next(s for s in value["signals"] if s["family"] == "coupling")["values"])
