import json
import unittest

from candidate_groups import candidate_group_limit, prepare_candidate_groups
from test_metrics import finding, prepare_memory


def complexity(files):
    results = []
    for path, value in files.items():
        row = finding("CyclomaticComplexMethod", f"Cyclomatic Complexity (complexity: {value})")
        row["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = path
        results.append(row)
    return json.dumps({"runs": [{"results": results}]})


def history(pairs):
    return "".join(f"--{index:x}--2026-01-01--a\n" + "".join(f"1\t0\t{path}\n" for path in paths)
                   for index, paths in enumerate(pairs, 1))


class CandidateGroupTests(unittest.TestCase):
    def assert_references(self, selections):
        signals = {row["signal"]: row for row in selections["signals"]}
        groups = {row["group"]: row for row in selections["candidate-groups"]}
        self.assertEqual(len(signals), len(selections["signals"]))
        self.assertEqual(len(groups), len(selections["candidate-groups"]))
        for group in groups.values():
            for ref in group["seed_signals"] + group["signals"] + [group["ordering_signal"]]:
                self.assertEqual(ref["path"], "selections/signals.jsonl")
                self.assertIn(ref["key"]["signal"], signals)
            self.assertEqual(len(group["signals"]), len({ref["key"]["signal"] for ref in group["signals"]}))
            for overlap in group["overlaps"]:
                other = groups[overlap["group"]]
                self.assertEqual(overlap["shared_files"], sorted(set(group["scope"]["files"]) & set(other["scope"]["files"])))
        for row in selections["investigation-queue"]:
            self.assertEqual(row["candidate_group"]["path"], "selections/candidate-groups.jsonl")
            self.assertIn(row["candidate_group"]["key"]["group"], groups)
            self.assertTrue(set(row["covered_by"]) <= groups.keys())

    def test_exact_scopes_merge_but_overlaps_do_not_expand(self):
        sources = {f"src/{name}.kt": {"package": name.lower()} for name in "ABC"}
        mappings = {f"{name.lower()}.{name}": f"src/{name}.kt" for name in "ABC"}
        pairs = [["src/A.kt", "src/B.kt"]] * 5 + [["src/B.kt", "src/C.kt"]] * 5
        value = prepare_memory({
            "dependencies": ("from,to\na.A,b.B\nb.B,a.A\nb.B,c.C\n", {"format": "class-csv"}),
            "history": (history(pairs), {}), "complexity": (complexity({"src/B.kt": 14}), {})}, sources, mappings)
        selections = value["selections"]
        groups = {tuple(row["scope"]["files"]): row for row in selections["candidate-groups"]}
        self.assertNotIn(("src/A.kt", "src/B.kt", "src/C.kt"), groups)
        left, right = groups["src/A.kt", "src/B.kt"], groups["src/B.kt", "src/C.kt"]
        self.assertIn({"group": right["group"], "shared_files": ["src/B.kt"]}, left["overlaps"])
        signals = {row["signal"]: row for row in selections["signals"]}
        self.assertEqual({signals[ref["key"]["signal"]]["family"] for ref in left["seed_signals"]}, {"cycle", "coupling"})
        risk = next(row for row in selections["signals"] if row["family"] == "complexity")
        self.assertTrue(all(any(ref["key"]["signal"] == risk["signal"] for ref in group["signals"]) for group in (left, right)))
        deferred = next(row for row in selections["investigation-queue"] if row["candidate_group"]["key"]["group"] == groups["src/B.kt",]["group"])
        self.assertFalse(deferred["selected"])
        self.assertTrue(deferred["covered_by"])
        self.assert_references(selections)

    def test_budget_preserves_deferred_groups_and_risk_order(self):
        sources = {f"src/{name}.kt": {"package": name.lower()} for name in ("A", "B", "High", "Low")}
        value = prepare_memory({
            "dependencies": ("from,to\na.A,b.B\nb.B,a.A\n", {"format": "class-csv"}),
            "complexity": (complexity({"src/Low.kt": 12, "src/High.kt": 30}), {})},
            sources, {"a.A": "src/A.kt", "b.B": "src/B.kt"}, {"candidate_group_limit": 2})
        groups = {row["group"]: row for row in value["selections"]["candidate-groups"]}
        queue = value["selections"]["investigation-queue"]
        selected = [groups[row["candidate_group"]["key"]["group"]] for row in queue if row["selected"]]
        self.assertEqual([row["scope"]["files"] for row in selected], [["src/A.kt", "src/B.kt"], ["src/High.kt"]])
        self.assertEqual(len(queue), 3)
        self.assertFalse(queue[-1]["selected"])
        self.assertIn("limit reached", queue[-1]["reason"])
        self.assertEqual(queue[-1]["covered_by"], [])

    def test_granularities_are_retained_when_the_file_scope_matches(self):
        value = prepare_memory({"dependencies": ("from,to\na.A,b.B\nb.B,a.A\n", {"format": "class-csv"})},
                               {"src/A.kt": {"package": "a"}, "src/B.kt": {"package": "b"}},
                               {"a.A": "src/A.kt", "b.B": "src/B.kt"}, {"modules": {"one": ["a"], "two": ["b"]}})
        selections = value["selections"]
        self.assertEqual(len(selections["candidate-groups"]), 1)
        self.assertEqual({row["references"][0]["path"] for row in selections["signals"]},
                         {f"metrics/cyclic-components/{level}.jsonl" for level in ("class", "package", "module")})
        self.assertTrue(selections["candidate-groups"][0]["source_available"])
        self.assert_references(selections)

    def test_strong_coupling_precedes_hotspots_and_weak_coupling(self):
        sources = {f"src/{name}.kt": {"package": name.lower()} for name in "ABC"}
        pairs = [["src/A.kt", "src/B.kt"]] * 5 + [["src/B.kt", "src/C.kt"]] * 5 + [["src/A.kt"]] * 10
        value = prepare_memory({
            "dependencies": ("from,to\na.A,b.B\nb.B,c.C\n", {"format": "class-csv"}),
            "history": (history(pairs), {})}, sources,
            {f"{name.lower()}.{name}": f"src/{name}.kt" for name in "ABC"}, {"candidate_group_limit": 2})
        groups = {row["group"]: row for row in value["selections"]["candidate-groups"]}
        queue = value["selections"]["investigation-queue"]
        selected = [groups[row["candidate_group"]["key"]["group"]]["scope"]["files"] for row in queue if row["selected"]]
        self.assertEqual(selected, [["src/B.kt", "src/C.kt"], ["src/A.kt"]])
        weak = next(row for row in queue if groups[row["candidate_group"]["key"]["group"]]["scope"]["files"] == ["src/A.kt", "src/B.kt"])
        self.assertIn("limit reached", weak["reason"])

    def test_usable_evidence_precedes_limited_evidence_within_a_category(self):
        value = prepare_memory({"complexity": (complexity({"src/High.kt": 30, "src/Low.kt": 12}), {})})
        signals = [{key: field for key, field in row.items() if key != "signal"} for row in value["selections"]["signals"]]
        for signal in signals:
            if signal["references"][0]["key"]["file"] == "src/High.kt":
                signal["suitability"] = "limited"
                signal["weights_MRS"] = [1, 1, 1]
        selections = prepare_candidate_groups({"candidate_group_limit": 1}, value["rows"], value["outcomes"], signals)
        selected = next(row for row in selections["investigation-queue"] if row["selected"])
        group = next(row for row in selections["candidate-groups"] if row["group"] == selected["candidate_group"]["key"]["group"])
        self.assertEqual(group["scope"]["files"], ["src/Low.kt"])

    def test_martin_distance_is_supporting_evidence_with_package_membership(self):
        value = prepare_memory({"dependencies": ("from,to\na.A,b.B\n", {"format": "class-csv"})},
                               {"src/A.kt": {"package": "a", "types": 5, "abstract": 0},
                                "src/B.kt": {"package": "b", "types": 5, "abstract": 0}})
        signal = next(row for row in value["selections"]["signals"] if row["family"] == "boundary")
        self.assertEqual(signal["references"][0]["key"], {"package": "b"})
        group = value["selections"]["candidate-groups"][0]
        self.assertEqual(group["scope"]["files"], ["src/B.kt"])
        self.assertEqual(group["category"], "supporting")

    def test_partial_mapping_never_merges_by_its_known_subset(self):
        value = prepare_memory({
            "dependencies": ("from,to\na.A,b.B\nb.B,a.A\na.Inner,b.Other\nb.Other,a.Inner\n", {"format": "class-csv"}),
            "complexity": (complexity({"src/A.kt": 15}), {})}, {"src/A.kt": {"package": "a"}},
            {"a.A": "src/A.kt", "a.Inner": "src/A.kt"})
        groups = value["selections"]["candidate-groups"]
        partial = [group for group in groups if group["scope"].get("unresolved_objects")]
        self.assertEqual(len(partial), 3)  # two class cycles and the distinct package cycle
        for group in partial:
            self.assertFalse(group["source_available"])
            self.assertEqual(group["signals"], group["seed_signals"])
            self.assertTrue(group["limitations"])
        self.assert_references(value["selections"])

    def test_source_free_parameter_finding_is_retained_without_a_number(self):
        row = finding("LongParameterList", "f(a: Pair<A,B>) exceeds threshold")
        value = prepare_memory({"complexity": (json.dumps({"runs": [{"results": [row]}]}), {})})
        group = value["selections"]["candidate-groups"][0]
        self.assertFalse(group["source_available"])
        self.assertEqual(group["category"], "supporting")
        self.assertIsNone(value["rows"]["parameter-list/declaration"][0]["value"])
        self.assertTrue(group["limitations"])
        self.assertTrue(value["selections"]["investigation-queue"][0]["selected"])

    def test_repeated_and_reordered_signals_produce_identical_groups(self):
        value = prepare_memory({"complexity": (complexity({"src/B.kt": 15, "src/A.kt": 15}), {})},
                               {"src/A.kt": {"package": "a"}, "src/B.kt": {"package": "b"}})
        signals = [{key: field for key, field in row.items() if key != "signal"} for row in value["selections"]["signals"]]
        first = prepare_candidate_groups({}, value["rows"], value["outcomes"], signals)
        second = prepare_candidate_groups({}, value["rows"], value["outcomes"], list(reversed(signals + signals)))
        self.assertEqual(first, second)
        self.assertEqual(len(first["signals"]), 2)
        self.assert_references(first)

    def test_unavailable_and_suppressed_evidence_does_not_seed_groups(self):
        row = finding("LongParameterList", "f(a) exceeds threshold")
        row["suppressions"] = [{"kind": "inSource"}]
        for value in (prepare_memory({}), prepare_memory({"complexity": (json.dumps({"runs": [{"results": [row]}]}), {})})):
            self.assertEqual(value["selections"]["signals"], [])
            self.assertEqual(value["selections"]["candidate-groups"], [])
            self.assertEqual(value["selections"]["investigation-queue"], [])

    def test_limit_is_explicit_and_rejects_non_integer_values(self):
        self.assertEqual(candidate_group_limit({}), 12)
        self.assertEqual(candidate_group_limit({"candidate_group_limit": 8}), 8)
        for value in (0, -1, True, None, "12", 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive integer"):
                candidate_group_limit({"candidate_group_limit": value})
