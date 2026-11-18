import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analysis import prepare_selections
from analysis_policy import PROJECT_POLICY, load_policy, read_json, validate_policy
from collection import run
from graph import module_views
from history import group_activity, history_view, parse_history
from measurements import CATALOG
from metrics import main
from parameters import parameter_count
from recommendations import markdown, rank
from test_metrics import DEFAULT_POLICY, card, card_markdown, finding, prepare_memory, resolved_policy


def select(measurements, overrides=None):
    rows = {name: [] for name in CATALOG}
    rows.update(measurements)
    return prepare_selections(rows, {name: {"status": "complete"} for name in CATALOG}, {},
                              resolved_policy(overrides))["signals"]


class AnalysisPolicyTests(unittest.TestCase):
    def test_shared_schema_accepts_full_and_partial_documents_and_preserves_siblings(self):
        override = {"signals": {"shape": {"parameter_list_minimum": 4}}}
        validate_policy(DEFAULT_POLICY)
        validate_policy(override)
        result = resolved_policy(override)
        self.assertEqual(result["signals"]["shape"]["parameter_list_minimum"], 4)
        integral_number = resolved_policy({"signals": {"shape": {"parameter_list_minimum": 4.0}}})
        self.assertIs(type(integral_number["signals"]["shape"]["parameter_list_minimum"]), int)
        self.assertEqual(result["signals"]["shape"]["method_length_minimum"], DEFAULT_POLICY["signals"]["shape"]["method_length_minimum"])
        result["signals"]["shape"]["method_length_minimum"] = 99
        self.assertNotEqual(DEFAULT_POLICY["signals"]["shape"]["method_length_minimum"], 99)
        with self.assertRaisesRegex(ValueError, "missing keys"):
            validate_policy(override, complete=True)

    def test_invalid_overrides_fail_instead_of_silently_using_defaults(self):
        cases = [None, [], {"signal": {}}, {"signals": {"shape": {"typo": 1}}},
                 {"signals": {"shape": {"parameter_list_minimum": True}}},
                 {"signals": {"shape": {"parameter_list_minimum": 2.5}}},
                 {"signals": {"boundary": {"distance_minimum": 1.1}}},
                 {"signals": {"coverage": {"maximum_line_coverage": float("nan")}}},
                 {"runtime": {"command_timeout_seconds": float("inf")}},
                 {"runtime": {"command_timeout_seconds": 0}},
                 {"measurements": {"changes_per_code": {"minimum_code_lines": 0}}},
                 {"recommendations": {"effect_points": {"local": 3, "substantial": 2}}},
                 {"recommendations": {"effect_points": {"not_shown": 1}}},
                 {"investigation": {"family_points": {"limited": 3, "usable": 2}}}]
        for override in cases:
            with self.subTest(override=override), self.assertRaises(ValueError):
                # Exercise the validator directly for falsey non-object inputs too.
                validate_policy(override)
                resolved_policy(override)
        with patch.object(Path, "read_text", return_value='{"signals": {}, "signals": {}}'):
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                read_json("policy.json")

    def test_project_path_is_automatic_and_invalid_project_json_is_not_ignored(self):
        original = read_json
        seen = []

        def read(path):
            if Path(path).as_posix().endswith(PROJECT_POLICY.as_posix()):
                seen.append(path)
                return {"signals": {"shape": {"parameter_list_minimum": 4}}}
            return original(path)

        with patch("analysis_policy.read_json", side_effect=read), patch.object(Path, "exists", return_value=True):
            self.assertEqual(load_policy("project")["signals"]["shape"]["parameter_list_minimum"], 4)
        self.assertEqual(len(seen), 1)
        with patch("analysis_policy.read_json", side_effect=ValueError("malformed policy")):
            with self.assertRaisesRegex(ValueError, "malformed policy"):
                load_policy("project")

    def test_policy_cli_requires_a_file_for_objects_and_reports_errors_on_stderr(self):
        for selection, diagnostic in (([], "--output"), (["--get", "signals"], "--output"),
                                      (["--get", "signals.shape.typo"], "Unknown policy key")):
            with self.subTest(selection=selection), patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                    patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(main(["policy", "--defaults", *selection]), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn(diagnostic, stderr.getvalue())

    def test_numeric_filters_use_overrides_and_keep_inclusive_and_strict_boundaries(self):
        mappings = [
            ("complexity", "cyclomatic_minimum", "cyclomatic-complexity/function", 7),
            ("complexity", "cognitive_minimum", "cognitive-complexity/function", 8),
            ("shape", "method_length_minimum", "method-length/function", 9),
            ("shape", "function_count_minimum", "function-count/declaration", 4),
            ("shape", "parameter_list_minimum", "parameter-list/declaration", 3),
            ("boundary", "distance_minimum", "distance/package", 0.4),
        ]
        for family, key, metric, threshold in mappings:
            row = {"file": "a.kt", "region": {}, "declaration": "f", "package": "a", "value": threshold}
            override = {"signals": {family: {key: threshold}}}
            with self.subTest(metric=metric):
                self.assertEqual(len(select({metric: [row]}, override)), 1)
                self.assertEqual(select({metric: [{**row, "value": threshold / 2}]}, override), [])
                self.assertEqual(select({metric: [{**row, "suppressed": True}]}, override), [])
        self.assertEqual(select({"crap-file/file": [{"file": "a.kt", "value": 12}]}, {"signals": {"crap": {"minimum_value": 12}}}), [])
        self.assertEqual(len(select({"crap-file/file": [{"file": "a.kt", "value": 13}]}, {"signals": {"crap": {"minimum_value": 12}}})), 1)
        self.assertEqual(select({"cyclic-components/package": [{"members": ["a", "b"]}]}, {"signals": {"cycle": {"minimum_members": 3}}}), [])

    def test_history_hotspot_and_coverage_filters_use_their_own_parameters(self):
        pair = {"left": "a.kt", "right": "b.kt", "cross_package": True, "average_frequency": 2, "shared": 2, "value": 20}
        override = {"signals": {"coupling": {"minimum_average_frequency": 2, "minimum_shared_commits": 2, "minimum_degree": 20}}}
        self.assertEqual(len(select({"coupling/file-pair": [pair]}, override)), 1)
        for field in ("average_frequency", "shared", "value"):
            self.assertEqual(select({"coupling/file-pair": [{**pair, field: 1}]}, override), [])
        rows = {"change-frequency/file": [{"file": "a.kt", "value": 2}],
                "line-coverage/file": [{"file": "a.kt", "value": .7}]}
        self.assertEqual(len(select(rows, {"signals": {"coverage": {"minimum_frequency": 2, "maximum_line_coverage": .8}}})), 1)
        self.assertEqual(select(rows, {"signals": {"coverage": {"minimum_frequency": 2, "maximum_line_coverage": .7}}}), [])
        rows = {"hotspot-in-frequency/file": [{"file": name, "value": score, "activity": 2, "visibility": .2}
                                              for name, score in (("a.kt", 9), ("b.kt", 8))]}
        override = {"signals": {"hotspot": {"top_count": 1, "minimum_frequency": 3, "minimum_visibility": .1}}}
        self.assertEqual(len(select(rows, override)), 1)
        override["signals"]["hotspot"]["minimum_frequency"] = 2
        self.assertEqual(len(select(rows, override)), 3)  # top entry plus both activity/visibility matches

    def test_measurement_population_window_and_formula_parameters_propagate(self):
        commits = parse_history("--a--2026-01-01--a\n1\t0\ta.kt\n1\t0\tb.kt\n--b--2026-01-03--a\n1\t0\ta.kt\n")
        policy = resolved_policy({"measurements": {"history": {"maximum_changeset_size": 1, "recent_days": 1},
                                                   "martin": {"minimum_types": 1},
                                                   "external_affinity": {"minimum_declared_fraction": .9}}})
        self.assertEqual(history_view(commits, policy)["coupling"], [])
        self.assertEqual(group_activity(commits, {"a.kt": "one", "b.kt": "one"}, policy)["one"]["recent_commits"], 1)
        view = module_views({("a.x", "b.x"): 5, ("a.x", "unknown.x"): 5}, {"A": ["a"], "B": ["b"]},
                            {"a.x": {"types": 1, "abstract": 0}}, policy)
        self.assertIn("a.x", view["martin"])
        self.assertEqual(view["external_affinity"]["a.x"]["category"], "grey")
        value = prepare_memory({
            "complexity": (json.dumps({"runs": [{"results": [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)")]}]}), {"complete_mcc": True}),
            "coverage": ("file,line_covered,line_total,branch_covered,branch_total\nsrc/Price.kt,2,10,0,0\n", {"format": "coverage-csv"}),
        }, {"src/Price.kt": {"package": "a"}}, policy={"measurements": {"crap": {"complexity_exponent": 1, "uncovered_exponent": 1}},
                                                      "signals": {"crap": {"minimum_value": 22}}})
        self.assertAlmostEqual(value["rows"]["crap-file/file"][0]["value"], 21.6)
        self.assertEqual(value["rows"]["crap-above-threshold/package"][0]["value"], 0)
        density = prepare_memory({
            "history": ("--a--2026-01-01--a\n1\t0\tsrc/Price.kt\n", {}),
            "sizes": (json.dumps([{"Name": "Kotlin", "Files": [{"Location": "src/Price.kt", "Code": 10, "Lines": 12, "Comment": 1, "Blank": 1}]}]), {}),
        }, policy={"measurements": {"changes_per_code": {"minimum_frequency": 1, "minimum_code_lines": 10, "code_line_unit": 50}}})
        self.assertEqual(density["rows"]["changes-per-code/file"][0]["value"], 5)

    def test_diagnostic_weights_family_points_and_recommendation_policy_are_separate(self):
        value = prepare_memory({"complexity": (json.dumps({"runs": [{"results": [finding("CyclomaticComplexMethod", "Cyclomatic Complexity (complexity: 12)")]}]}), {})},
                               policy={"evidence": {"weights": {"complexity": {"modularity": 4}}},
                                       "investigation": {"family_points": {"usable": 5}}})
        self.assertEqual(value["selections"]["signals"][0]["evidence_weights"]["modularity"], 4)
        self.assertEqual(value["selections"]["candidate-groups"][0]["investigation_score"], 5)
        limited = select({"cyclomatic-complexity/function": [{"file": "a.kt", "region": {}, "declaration": "f",
                                                            "value": 12, "status": "measured_subset"}]},
                         {"evidence": {"limited_weight_cap": 2, "weights": {"complexity": {"modularity": 4}}}})
        self.assertEqual(limited[0]["evidence_weights"]["modularity"], 2)
        policy = resolved_policy({"recommendations": {"report_limit": 1, "effect_points": {"local": 2, "substantial": 5},
                                                        "criterion_weights": {"modularity": 3}}})
        result = rank({"recommendations": [card("M", ("local", "not_shown", "not_shown")),
                                            card("R", ("not_shown", "substantial", "not_shown"))]},
                      {"src/Price.kt": {}}, read_card=lambda path: card_markdown(Path(path).stem), policy=policy)
        self.assertEqual(result["priority_groups"], [["M"], ["R"]])
        self.assertEqual([c["priority_score"] for c in result["recommendations"]], [6, 5])
        table, further = markdown(result).split("## Further directions")
        self.assertNotIn("[R:", table)
        self.assertIn("[R:", further)

    def test_fractional_criterion_weights_preserve_ties(self):
        policy = resolved_policy({"recommendations": {"criterion_weights": {
            "modularity": .1, "regression_risk": .2, "change_cost_reduction": .3}}})
        result = rank({"recommendations": [card("MR", ("local", "local", "not_shown")),
                                            card("C", ("not_shown", "not_shown", "local"))]},
                      {"src/Price.kt": {}}, read_card=lambda path: card_markdown(Path(path).stem), policy=policy)
        self.assertEqual(result["priority_groups"], [["C", "MR"]])

    def test_command_timeout_and_error_tail_are_resolved_parameters(self):
        process = Mock(returncode=1)
        process.communicate.return_value = (b"", b"prefix-detail")
        policy = resolved_policy({"runtime": {"command_timeout_seconds": 7, "stderr_tail_characters": 6}})
        with patch("collection.subprocess.Popen", return_value=process), self.assertRaisesRegex(ValueError, "detail$") as error:
            run(["tool"], ".", policy)
        self.assertNotIn("prefix", str(error.exception))
        process.communicate.assert_called_once_with(timeout=7)


class ParameterListTests(unittest.TestCase):
    def test_complete_signatures_count_parameters_not_nested_commas_or_detector_threshold(self):
        cases = [
            ("The function f()", 0),
            ("The constructor(id: Id)", 1),
            ("The function f(a: Map<A, List<B>>, b: (A, B) -> Pair<C, D>)", 2),
            ('The function f(@A("x,y") a: String = "a,b", b: (A, B) -> C = { a, b -> c })', 2),
            ('The function f(a: String = ") has too many parameters.", b: Int)', 2),
            ("The function `f(x)`(vararg p: Pair<A, B>, /* outer /* inner */ */ q: Int,)", 2),
        ]
        for signature, expected in cases:
            with self.subTest(signature=signature):
                self.assertEqual(parameter_count(signature + " has too many parameters. The current threshold is set to 1."), expected)
        for signature in ("The function f(a: Pair<A, B)", "The function f(a)", "The function f(...)",
                          'The function f(a: String = "unterminated)', "The function f(a: Boolean = x < y)"):
            with self.subTest(signature=signature):
                self.assertIsNone(parameter_count(signature + " has too many parameters. threshold 1"))

    def test_minimal_detector_threshold_does_not_select_every_parameter_finding(self):
        row = finding("LongParameterList", "The function f(a: Pair<A,B>, b: (A,B) -> C) has too many parameters. The current threshold is set to 1.")
        payload = {"complexity": (json.dumps({"runs": [{"results": [row]}]}), {})}
        initial = prepare_memory(payload)
        self.assertEqual(initial["rows"]["parameter-list/declaration"][0]["value"], 2)
        self.assertEqual(initial["selections"]["signals"], [])
        selected = prepare_memory(payload, policy={"signals": {"shape": {"parameter_list_minimum": 2}}})
        self.assertEqual(len(selected["selections"]["signals"]), 1)
        self.assertEqual(selected["selections"]["signals"][0]["condition"], "value >= 2")
        self.assertFalse(selected["selections"]["candidate-groups"][0]["source_available"])
