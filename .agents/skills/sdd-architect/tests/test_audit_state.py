from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audit_state import (ASSETS, audit_directory, check_audit_state, main, parse_json,
                         read_json, validate_audit_state, write_audit_state)


def initial_state():
    return read_json(ASSETS / "audit-state.example.json")


def add_assignment(state, records, identity="collect-1", *, phase="evidence", accepted=False):
    scope = {"project": "project", "work": state["report"], "task": None}
    prefix = f"assignments/{identity}/"
    records[prefix + "request.json"] = {
        "report": state["report"], "phase": phase, "role": "sdd-spec.explorer",
        "assignment": {"id": identity, "scope": scope, "outputs": [f"outputs/{identity}.json"]},
    }
    row = {
        "id": identity,
        "assessment": {"status": "accepted" if accepted else "pending",
                       "reason": "Verified the assigned result." if accepted else None, "next_assignment": None},
        "host_observation": {"worker_id": None, "state": "unknown", "observed_at": None, "source": None},
    }
    if accepted:
        row["host_observation"] = {"worker_id": "worker-" + identity, "state": "stopped",
                                   "observed_at": "2026-11-15T12:00:01Z", "source": "host stopped observation"}
        records[prefix + "launch.json"] = {"worker_id": "worker-" + identity}
        records[prefix + "result.json"] = {
            "assignment_id": identity, "report": state["report"], "phase": phase,
            "role": "sdd-spec.explorer", "scope": scope, "status": "completed",
            "writing_stopped": True, "artifacts": [f"outputs/{identity}.json"],
        }
        records[f"outputs/{identity}.json"] = {}
    state["assignments"].append(row)
    return row


def check(state, records):
    def read(path):
        if path not in records:
            raise FileNotFoundError(path)
        return records[path]
    return check_audit_state(state, read, lambda path, kind: path in records)


class AuditStateTests(unittest.TestCase):
    def test_initial_state_has_an_explicit_next_action_and_unknown_observations(self):
        state = initial_state()
        self.assertIs(validate_audit_state(state), state)
        self.assertEqual(check(state, {}), [])
        self.assertIsNone(state["active_assignment"])

    def test_schema_rejects_missing_unknown_and_mistyped_control_fields(self):
        for key, value in (("schema_version", True), ("schema_version", 2), ("phase", "finished"),
                           ("route", "partial"), ("objective", "  "), ("constraints", "none")):
            with self.subTest(key=key, value=value):
                state = initial_state()
                state[key] = value
                with self.assertRaises(ValueError):
                    validate_audit_state(state)
        for alteration in ("missing", "extra"):
            state = initial_state()
            if alteration == "missing":
                del state["basis"]["decisions"]
            else:
                state["basis"]["source_revision"] = "unrequested gate"
            with self.subTest(alteration=alteration), self.assertRaisesRegex(ValueError, "keys"):
                validate_audit_state(state)

    def test_json_rejects_ambiguous_keys_and_non_finite_values(self):
        for text in ('{"phase":"evidence","phase":"complete"}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_json(text)

    def test_assignment_references_are_unique_contained_and_acyclic(self):
        for identity in ("../outside", "a/b", "a\n"):
            state = initial_state()
            add_assignment(state, {}, identity)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                validate_audit_state(state)
        state = initial_state()
        row = add_assignment(state, {})
        state["assignments"].append(deepcopy(row))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_audit_state(state)
        state["assignments"].pop()
        state["active_assignment"] = "absent"
        with self.assertRaisesRegex(ValueError, "Unknown assignment"):
            validate_audit_state(state)
        state["active_assignment"] = None
        row["assessment"] = {"status": "follow_up", "reason": "More evidence needed", "next_assignment": row["id"]}
        with self.assertRaisesRegex(ValueError, "cyclic"):
            validate_audit_state(state)

    def test_known_host_state_needs_observation_evidence(self):
        for field, value in (("worker_id", None), ("source", None), ("observed_at", None),
                             ("observed_at", "2026-11-15"), ("observed_at", "2026-11-15T12:00:00+03:00")):
            state = initial_state()
            row = add_assignment(state, {}, accepted=True)
            row["host_observation"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_audit_state(state)

    def test_completed_worker_result_does_not_accept_it_or_advance_phase(self):
        state, records = initial_state(), {}
        row = add_assignment(state, records, accepted=True)
        row["assessment"] = {"status": "pending", "reason": None, "next_assignment": None}
        state["active_assignment"] = row["id"]
        state["phase"] = "evidence"
        before = deepcopy(state)
        self.assertEqual(check(state, records), [])
        self.assertEqual(state, before)

    def test_acceptance_checks_worker_claim_host_observation_and_primary_output(self):
        for field, value in (("status", "partial"), ("writing_stopped", False), ("artifacts", []),
                             ("artifacts", ["lost-output.json"])):
            state, records = initial_state(), {}
            add_assignment(state, records, accepted=True)
            records["assignments/collect-1/result.json"][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(check(state, records))
        state, records = initial_state(), {}
        row = add_assignment(state, records, accepted=True)
        row["host_observation"]["state"] = "unknown"
        self.assertTrue(any("host stop" in issue for issue in check(state, records)))

    def test_result_identity_scope_and_request_shape_are_checked(self):
        for field, value in (("assignment_id", "other"), ("report", "other"), ("phase", "report"),
                             ("role", "other"), ("scope", {"project": "other", "work": None, "task": None})):
            state, records = initial_state(), {}
            add_assignment(state, records, accepted=True)
            records["assignments/collect-1/result.json"][field] = value
            with self.subTest(field=field):
                self.assertTrue(any("identity/scope" in issue for issue in check(state, records)))
        records["assignments/collect-1/request.json"]["assignment"] = None
        self.assertTrue(any("assignment object" in issue for issue in check(state, records)))

    def test_host_observation_is_bound_to_the_actual_launch_worker(self):
        state, records = initial_state(), {}
        row = add_assignment(state, records, accepted=True)
        row["host_observation"]["worker_id"] = "different-worker"
        self.assertTrue(any("does not match launch" in issue for issue in check(state, records)))
        records["assignments/collect-1/launch.json"]["worker_id"] = None
        self.assertTrue(any("recover the launch worker_id" in issue for issue in check(state, records)))

    def test_malformed_worker_status_is_reported_as_a_gap(self):
        state, records = initial_state(), {}
        add_assignment(state, records, accepted=True)
        records["assignments/collect-1/result.json"]["status"] = []
        self.assertTrue(any("unknown worker result status" in issue for issue in check(state, records)))

    def test_missing_evidence_stays_a_gap_with_the_saved_assessment_unchanged(self):
        state, records = initial_state(), {}
        add_assignment(state, records, accepted=True)
        del records["assignments/collect-1/result.json"]
        state["basis"]["artifacts"] = ["lost-collection.json"]
        state["blockers"] = ["Recover the missing result and collection."]
        before = deepcopy(state)
        issues = check(state, records)
        self.assertTrue(any("result.json" in issue for issue in issues))
        self.assertTrue(any("lost-collection" in issue for issue in issues))
        self.assertEqual(state, before)

    def test_follow_up_requires_a_stopped_previous_writer_and_an_explicit_link(self):
        state, records = initial_state(), {}
        previous = add_assignment(state, records, accepted=True)
        previous["assessment"] = {"status": "follow_up", "reason": "Collect the missing source", "next_assignment": "collect-2"}
        records["assignments/collect-1/result.json"]["status"] = "partial"
        add_assignment(state, records, "collect-2")
        state["active_assignment"], state["phase"] = "collect-2", "evidence"
        self.assertEqual(check(state, records), [])
        previous["host_observation"]["state"] = "unknown"
        self.assertTrue(any("previous writer" in issue for issue in check(state, records)))
        previous["host_observation"]["state"] = "stopped"
        previous["assessment"]["next_assignment"] = None
        self.assertTrue(any("link its follow-up" in issue for issue in check(state, records)))

    def test_completion_requires_finished_work_and_the_full_publication_result(self):
        state, records = initial_state(), {"report.md": {}, "../../plan/plan.md": {}}
        state.update(phase="complete", next_step=None)
        state["plan"]["path"] = "../../plan/plan.md"
        self.assertTrue(any("publication assignment" in issue for issue in check(state, records)))
        add_assignment(state, records, "publish-1", phase="publication", accepted=True)
        self.assertEqual(check(state, records), [])
        state["plan"]["remaining"] = ["Add the card's missing table row"]
        with self.assertRaisesRegex(ValueError, "unfinished"):
            validate_audit_state(state)
        state["plan"]["remaining"] = []
        state["assignments"][0]["assessment"] = {"status": "pending", "reason": None, "next_assignment": None}
        with self.assertRaisesRegex(ValueError, "accepted result"):
            validate_audit_state(state)

    def test_focused_completion_retains_the_partial_result_and_finished_follow_up(self):
        state, records = initial_state(), {"report.md": {}, "../../plan/plan.md": {}}
        first = add_assignment(state, records, accepted=True)
        first["assessment"] = {"status": "follow_up", "reason": "Remaining question", "next_assignment": "collect-2"}
        records["assignments/collect-1/result.json"]["status"] = "partial"
        add_assignment(state, records, "collect-2", accepted=True)
        state.update(route="focused", phase="complete", next_step=None)
        state["plan"]["path"] = "../../plan/plan.md"
        self.assertEqual(check(state, records), [])
        state["phase"] = "publication"
        with self.assertRaisesRegex(ValueError, "full route"):
            validate_audit_state(state)

    def test_cli_atomic_updates_preserve_old_state_on_failure_and_report_gaps(self):
        # Risk: an interrupted flush/replace can lose the only continuation record.
        # Real files verify replace, cleanup and UTF-8 bytes; mocks alone cannot verify these effects.
        with tempfile.TemporaryDirectory(prefix="architect-state-") as temporary:
            audit = Path(temporary) / "memory/tech-debt/audits/2026-11-15T12-00-00Z"
            state = initial_state()
            state["objective"] = "Продолжить аудит без потери решений"
            with patch("sys.stdin", io.StringIO(json.dumps(state, ensure_ascii=False))), patch("sys.stdout", io.StringIO()):
                self.assertEqual(main(["write", "--report-dir", str(audit)]), 0)
            target = audit / "state.json"
            original = target.read_bytes()
            completed = deepcopy(state)
            completed.update(phase="complete", next_step=None)
            with self.assertRaisesRegex(ValueError, "Cannot complete audit"):
                write_audit_state(audit, completed)
            self.assertEqual(target.read_bytes(), original)
            changed = deepcopy(state)
            changed["basis"]["artifacts"] = ["lost.json"]
            for operation in ("audit_state.os.fsync", "audit_state.os.replace"):
                with patch(operation, side_effect=OSError("interrupted")):
                    with self.assertRaisesRegex(OSError, "interrupted"):
                        write_audit_state(audit, changed)
                self.assertEqual(target.read_bytes(), original)
                self.assertEqual(list(audit.iterdir()), [target])
            write_audit_state(audit, changed)
            with patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(main(["read", "--report-dir", str(audit)]), 0)
                self.assertEqual(json.loads(output.getvalue()), changed)
            with patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(main(["check", "--report-dir", str(audit)]), 1)
                self.assertIn("lost.json", output.getvalue())
            changed["phase"] = "invalid"
            saved = target.read_bytes()
            with self.assertRaises(ValueError):
                write_audit_state(audit, changed)
            self.assertEqual(target.read_bytes(), saved)

    def test_state_storage_requires_an_audit_directory(self):
        with self.assertRaisesRegex(ValueError, "audits"):
            audit_directory(Path("unrelated-state"))
