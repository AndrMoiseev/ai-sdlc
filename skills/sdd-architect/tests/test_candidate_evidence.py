import unittest
from unittest.mock import patch

from candidate_evidence import class_dependencies, joint_changes
from measurements import read_keyed_rows


class CandidateEvidenceTests(unittest.TestCase):
    def test_joint_changes_keep_bulk_changes_distinguishable_from_coupling_support(self):
        def commit(identity, files):
            return {"commit": identity, "date": "2026-11-18", "changeset_size": len(files),
                    "changes": [{"file": file, "added": 1, "deleted": 0, "binary": False} for file in files]}

        commits = [commit("a", ["A"]), commit("b", ["A", "B"]), commit("c", ["A", "B", "C"])]
        rows = joint_changes({"A", "B"}, commits, 2)
        self.assertEqual([row["reference"]["key"]["commit"] for row in rows], ["b", "c"])
        self.assertEqual([row["included_in_coupling"] for row in rows], [True, False])
        self.assertEqual(rows[1]["changeset_size"], 3)
        self.assertEqual(rows[1]["changes"], commits[2]["changes"][:2])
        with self.assertRaisesRegex(ValueError, "distinct"):
            joint_changes({"A"}, commits, 2)

    def test_direct_edges_retain_direction_and_missing_mappings(self):
        mappings = [{"class": name, "file": name + ".kt"} for name in ("A", "B")]
        pairs = [("B", "A"), ("A", "External"), ("B", "Other")]
        result = class_dependencies({"A.kt", "C.kt"}, mappings, [{"from": a, "to": b} for a, b in pairs])
        self.assertEqual([(row["from_file"], row["to_file"]) for row in result["edges"]],
                         [("B.kt", "A.kt"), ("A.kt", None)])
        self.assertEqual(result["edges"][1]["reference"]["key"], {"from": "A", "to": "External"})
        self.assertEqual(result["files_without_mapped_classes"], ["C.kt"])
        self.assertEqual(result["unmapped_graph_class_count"], 2)

    def test_batch_lookup_reads_once_and_requires_unique_matches(self):
        keys = [{"signal": "a"}, {"signal": "b"}]
        with patch("measurements.read_jsonl", return_value=keys) as read:
            self.assertEqual(read_keyed_rows(None, "signals", ["signal"], keys + keys), keys)
            read.assert_called_once()
        for rows, message in ((keys[:1], "Missing"), (keys + keys, "Duplicate")):
            with patch("measurements.read_jsonl", return_value=rows), self.assertRaisesRegex(ValueError, message):
                read_keyed_rows(None, "signals", ["signal"], keys)
