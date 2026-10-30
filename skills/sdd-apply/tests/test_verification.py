from lib import artifact_storage as artifacts
import pytest
from pathlib import Path


@pytest.mark.parametrize("addition_kind", ["command", "procedure"])
def test_verifier_gap_extends_green_ab_before_review(execution_checkpoint, addition_kind):
    from copy import deepcopy
    import sys
    driver = execution_checkpoint("pending")
    driver.worktree()
    command = driver.task["plan"]["verification"][0]["run"]["command"]
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [
        {"id": "B", "source": "fixture", "criteria": ["AC-one"], "run": {"command": command}}]})
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt", "check.py"]})
    driver.run_checks("baseline")
    (driver.root / "result.txt").write_text("fixture implementation\n")
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    verifier = "verifier"
    stage = "independent"
    previous = driver.task
    checks = deepcopy(previous["checks"])
    result = driver.conclude(role=verifier, outcome="unavailable", check_request="Add explicit subtraction coverage")
    conclusion = result["verification_result"]["id"]
    addition = {"id": "C", "source": "verifier gap", "criteria": ["AC-one"],
                "run": {"command": [sys.executable, "-B", "-c", "assert 5 - 3 == 2"]}}
    if addition_kind == "procedure":
        addition.update(run={"procedure": "check.py"}, execution_kind="deterministic")
    driver.send("checks_extend", {"verification_result": conclusion, "additional": [addition]})
    expanded = driver.task
    assert expanded["checks"][:2] == checks
    assert [check["id"] for check in expanded["checks"]] == ["plan-1", "B", "C"]
    assert expanded["check_registry"]["revision"] == previous["check_registry"]["revision"] + 1
    assert expanded["evidence"] == previous["evidence"]
    for field in ("test_repair_cycles_started", "review_rounds_started", "active_review", "active_repair", "last_check_failed"):
        assert expanded[field] == previous[field]
    driver.role("gap-reviewer", "reviewer")
    with pytest.raises(ValueError):
        driver.send("review_start", {"role_id": "gap-reviewer"})
    if addition_kind == "procedure":
        driver.explorer("procedure-explorer", stage)
        driver.send("procedure_begin", {"role_id": "procedure-explorer", "stage": stage, "check_id": "C"})
        driver.send("procedure_result", {"role_id": "procedure-explorer", "check_id": "C", "outcome": "passed",
            "steps": ["Synthetic deterministic check inspected"], "trace": "synthetic-unit-test"})
    result = driver.run_checks(stage)
    assert result["outcome"] == "passed"
    assert result["summary"]["requested_check_ids"] == ["plan-1", "B", "C"]
    with pytest.raises(ValueError, match="registry or applicable check attempt changed"):
        driver.send("review_start", {"role_id": "gap-reviewer"})
    driver.conclude(role=verifier)
    assert driver.send("review_start", {"role_id": "gap-reviewer"})["round"] == previous["review_rounds_started"] + 1


@pytest.mark.parametrize("damage", ["passed", "foreign", "stale", "no_request", "foreign_criterion", "both_bases"])
def test_verifier_extension_rejects_invalid_basis(execution_checkpoint, damage):
    driver = execution_checkpoint("verified")
    outcome = "passed" if damage == "passed" else "failed"
    request = None if damage in {"passed", "no_request"} else "Add boundary coverage"
    result = driver.conclude(outcome=outcome, check_request=request)
    conclusion = result["verification_result"]["id"]
    addition = {"id": "C", "source": "gap", "criteria": ["AC-one"],
                "run": driver.task["checks"][0]["run"]}
    value = {"verification_result": conclusion, "additional": [addition]}
    if damage == "foreign":
        value["verification_result"] = "another-task-conclusion"
    elif damage == "stale":
        driver.run_checks("independent")
    elif damage == "foreign_criterion":
        addition["criteria"] = ["AC-another-task"]
    elif damage == "both_bases":
        value["review_round"] = "unrelated-round"
    before = driver.task
    with pytest.raises(ValueError):
        driver.send("checks_extend", value)
    assert driver.task == before


def test_gap_preparation_reopens_executor_without_fabricated_failure(execution_checkpoint):
    driver = execution_checkpoint("verified")
    result = driver.conclude(outcome="failed", check_request="Prepare another exact assertion")
    conclusion = result["verification_result"]["id"]
    driver.send("checks_extend", {"verification_result": conclusion, "additional": [
        {"id": "C", "source": "gap", "criteria": ["AC-one"], "run": driver.task["checks"][0]["run"]}]})
    assert driver.send("repair", {"reason": "Prepare verifier-requested assertion", "defect_evidence": conclusion}) == {
        "status": "repairing", "cycle": None}
    assert driver.task["test_repair_cycles_started"] == driver.task["review_rounds_started"] == 0
    driver.freeze()
    assert driver.verify()["outcome"] == "passed"
    assert driver.review()["status"] == "integrating"


@pytest.mark.parametrize("target", ["result.txt", "sdd/changes/demo/design.md"])
def test_successful_command_cannot_hide_changes_during_verification(execution_checkpoint, target):
    import json
    from lib.verification import current
    driver = execution_checkpoint("started")
    (driver.root / "check.py").write_text(
        "from pathlib import Path\n" + f"Path({target!r}).write_text('changed by check')\n")
    driver.freeze()
    before = current(driver.state, driver.task)
    result = driver.verify()
    assert result["outcome"] == "failed"
    log = json.loads(artifacts.read_text(driver.directory / result["log"]))
    assert log["outputs"][0]["exit_code"] == 0
    assert log["before"] == before and log["after"] != before
    assert driver.task["evidence"][-1]["outcome"] == "stale"


def test_independent_run_catches_defect(execution_checkpoint):
    driver = execution_checkpoint("started")
    project = driver.root
    (project / "check.py").write_text("assert False, 'real defect'\n")
    driver.freeze()
    assert driver.verify()["outcome"] == "failed"
    assert driver.task["last_check_failed"]
    assert driver.task["test_repair_cycles_started"] == 0
    with pytest.raises(ValueError, match="reserve"):
        driver.verify()
    driver.role("reviewer", "reviewer")
    with pytest.raises(ValueError, match="required check"):
        driver.send("review_start", {"role_id": "reviewer"})


def test_stale_candidate_and_log_tampering(execution_checkpoint):
    driver = execution_checkpoint("verified")
    project = driver.root
    log = driver.directory / driver.task["evidence"][-1]["log"]
    artifacts.write(log, "forged")
    driver.role("reviewer", "reviewer")
    with pytest.raises(ValueError):
        driver.send("review_start", {"role_id": "reviewer"})
    (project / "result.txt").write_text("changed")
    with pytest.raises(ValueError, match="changed|before verification"):
        driver.verify()


def test_author_cannot_verify_and_writer_must_stop(execution_checkpoint):
    driver = execution_checkpoint("started")
    with pytest.raises(ValueError, match="finish"):
        driver.send("candidate")
    driver.freeze()
    with pytest.raises(ValueError, match="independent"):
        driver.send("check_run", {"role_id": "author", "stage": "independent"})


def test_additional_review_checks_invalidate_previous_pass(execution_checkpoint):
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    command = driver.task["checks"][0]["run"]["command"]
    driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [{"id": "extra", "source": "review", "criteria": ["AC-one"], "run": {"command": command}}]})
    driver.role("new-reviewer", "reviewer")
    with pytest.raises(ValueError, match="Every required"):
        driver.send("review_start", {"role_id": "new-reviewer"})
    assert driver.verify()["outcome"] == "passed"
    assert driver.send("review_start", {"role_id": "new-reviewer"})["round"] == 2


@pytest.mark.native_process
def test_timeout_is_unavailable_and_stops_own_process(tmp_path):
    import sys
    from lib.inputs import spec_modules
    run_command = spec_modules("check_runner").run_command
    result = run_command([sys.executable, "-B", "-c", "import time; time.sleep(30)"], tmp_path, .05)
    assert result["outcome"] == "unavailable"
    assert result["exit_code"] is None
    assert result["duration_seconds"] < 10


def test_initial_failing_check_blocks_plan(driver, project):
    from repository_support import stage, commit
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}})
    (project / "check.py").write_text("assert False\n")
    stage(project, "check.py")
    commit(project, "Existing failing check")
    from repository_support import accept_execution_source
    accept_execution_source(driver)
    driver.worktree()
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt"]})
    assert driver.run_checks("baseline")["outcome"] == "failed"
    assert driver.state["status"] == "blocked"
    assert driver.state["blockers"][0]["reason"] == "baseline_failed"


@pytest.mark.native_process
def test_arguments_are_literal_and_paths_with_spaces_work(tmp_path):
    import json
    import sys
    from lib.inputs import spec_modules
    run_command = spec_modules("check_runner").run_command
    cwd = tmp_path / "working directory"
    cwd.mkdir()
    script = cwd / "echo arguments.py"
    script.write_text("import json, sys; print(json.dumps(sys.argv[1:]))\n")
    arguments = ["", "two words", 'a"quote', "trailing\\", "&&", ";", "|", ">", "*.py", "$HOME", "%TEMP%", "$(echo unexpected)"]
    command = [sys.executable, "-B", str(script), *arguments]
    result = run_command(command, cwd, 10)
    assert result["outcome"] == "passed", result
    assert json.loads(result["stdout"]) == arguments
    assert result["command"] == command
    assert list(cwd.iterdir()) == [script]


@pytest.mark.parametrize("command", ["echo unsafe > marker", [], [""], [None], ["runner", "bad\0arg"]])
@pytest.mark.native_process
def test_invalid_or_legacy_command_never_starts_process(tmp_path, monkeypatch, command):
    from lib import verification
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid command reached subprocess")
    monkeypatch.setattr(verification.check_runner.subprocess, "Popen", unexpected)
    result = verification.check_runner.run_command(command, tmp_path, 10)
    assert result["outcome"] == "unavailable"
    assert result["limitation"] == "command_format"
    assert result["exit_code"] is None


@pytest.mark.native_process
def test_nonzero_exit_and_missing_executable(tmp_path):
    import sys
    from lib.inputs import spec_modules
    run_command = spec_modules("check_runner").run_command
    result = run_command([sys.executable, "-B", "-c", "import sys; sys.stderr.write('failure'); sys.exit(7)"], tmp_path, 10)
    assert result["outcome"] == "failed"
    assert result["exit_code"] == 7
    assert result["stderr"].endswith("failure")
    result = run_command([str(tmp_path / "missing-executable")], tmp_path, 10)
    assert result["outcome"] == "unavailable"
    assert result["exit_code"] is None


@pytest.mark.native_process
def test_explicit_shell_script(tmp_path):
    import os
    import shutil
    from lib.inputs import spec_modules
    run_command = spec_modules("check_runner").run_command
    if os.name == "nt":
        script = tmp_path / "verify.cmd"
        script.write_text("@echo off\necho explicit-shell\nexit /b 7\n")
        command = [os.environ["COMSPEC"], "/d", "/c", script.name]
    else:
        script = tmp_path / "verify.sh"
        script.write_text("echo explicit-shell\nexit 7\n")
        command = [shutil.which("sh"), str(script)]
    result = run_command(command, tmp_path, 10)
    assert result["stdout"].strip() == "explicit-shell"
    assert result["exit_code"] == 7
    assert result["outcome"] == "failed"


def test_additional_check_rejects_string_command(driver):
    with pytest.raises(ValueError, match="argument array"):
        driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [{"id": "extra", "source": "ci", "run": {"command": "pytest"}}]})
    assert not driver.task["checks"]


def test_extension_rejects_string_command(execution_checkpoint):
    driver = execution_checkpoint("verified")
    driver.review(verdict="more_checks")
    with pytest.raises(ValueError, match="argument array"):
        driver.send("checks_extend", {"review_round": driver.task["reviews"][-1]["round_id"], "additional": [{"id": "extra", "source": "review", "criteria": ["AC-one"], "run": {"command": "pytest"}}]})
    assert len(driver.task["checks"]) == 1


def test_summary_exposes_full_raw_log_without_reexecution(execution_checkpoint, monkeypatch):
    import json
    import os
    from lib import verification
    from lib.state import read_object
    driver = execution_checkpoint("started")
    (driver.root / "check.py").write_text("print('diagnostic-' * 1000)\n")
    driver.freeze()
    driver.role("verifier", "verifier")
    explorer_id = "summary-independent-explorer"
    result = driver.run_checks("independent", ident=explorer_id)
    assert result["outcome"] == "passed"
    aggregate = result["summary"]
    assert aggregate["requested_check_ids"] == aggregate["completed_check_ids"] == ["plan-1"]
    assert aggregate["missing_check_ids"] == [] and aggregate["evidence_complete"] is True
    def unexpected(*args):
        pytest.fail("Reading evidence must not execute another check")
    monkeypatch.setattr(verification.check_runner, "run_command", unexpected)
    machine = read_object(driver.directory, aggregate["checks"][0])
    raw = read_object(driver.directory, machine["artifacts"]["stdout"])
    assert raw["content"] == "diagnostic-" * 1000 + os.linesep
    assert machine["excerpt"]["text"] == raw["content"][-4096:]
    assert machine["excerpt"]["truncated"] is True
    assert machine["configuration"]["sha256"]
    assert machine["basis_before"] == machine["basis_after"]
    assert machine["assignment_id"] == machine["role_id"] == explorer_id
    assert driver.state["roles"][explorer_id]["kind"] == "explorer"
    assert driver.state["roles"][explorer_id]["assignment"]["id"] == explorer_id
    assert machine["role_trace"]["launch_ref"] == "synthetic-unit-test"
    assert machine["test_counts"]["passed"] is None
    record = json.loads(artifacts.read_text(driver.directory / result["log"]))
    assert "stdout" not in record["outputs"][0] and "stderr" not in record["outputs"][0]
    assert verification.valid_evidence(driver.state, driver.task, driver.directory)


def test_missing_required_report_blocks_baseline_even_with_exit_zero(execution_checkpoint):
    import json
    driver = execution_checkpoint("pending")
    driver.worktree()
    command = driver.task["plan"]["verification"][0]["run"]["command"]
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []},
        "additional": [{"id": "report-check", "source": "fixture-contract", "criteria": ["AC-one"],
            "run": {"command": command}, "configuration": {"structured_reports": [
                {"format": "pytest-junit", "path": "missing.xml", "required": True}]}}]})
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt", "check.py"]})
    result = driver.run_checks("baseline")
    assert result["outcome"] == "unavailable" and result["summary"]["evidence_complete"] is False
    assert driver.state["status"] == "blocked"
    record = json.loads(artifacts.read_text(driver.directory / result["log"]))
    assert record["outputs"][1]["exit_code"] == 0 and record["outputs"][1]["outcome"] == "passed"


@pytest.mark.parametrize("damage", ["digest", "missing", "foreign", "basis"])
def test_summary_raw_integrity_blocks_gate(execution_checkpoint, damage):
    import json
    from lib.common import Rejected, digest, write_json
    from lib.state_objects import StateObjects
    from lib.verification import valid_evidence
    driver = execution_checkpoint("verified")
    state, task = driver.state, driver.task
    evidence = task["evidence"][-1]
    path = driver.directory / evidence["log"]
    record = json.loads(artifacts.read_text(path))
    objects = StateObjects(driver.directory)
    aggregate = objects.get(record["summary"])
    machine = objects.get(record["outputs"][0]["summary"])
    reference = machine["artifacts"]["stdout"]
    if damage == "digest":
        artifacts.write(driver.directory / reference["path"], "forged bytes")
    elif damage == "missing":
        artifacts.remove(driver.directory / reference["path"])
    else:
        if damage == "foreign":
            raw = objects.get(reference)
            raw["identity"]["run_id"] = "foreign-run"
            machine["artifacts"]["stdout"] = objects.put(raw)
        else:
            machine["basis_before"] = objects.put({"head": "foreign-head"})
        changed = objects.put(machine)
        record["outputs"][0]["summary"] = changed
        aggregate["checks"][0] = changed
        record["summary"] = objects.put(aggregate)
        write_json(path, record)
        # Keep outer hashes consistent to exercise the nested identity gate.
        for item in task["evidence"]:
            if item["log"] == evidence["log"]:
                item["log_hash"] = digest(artifacts.read_bytes(path))
    with pytest.raises(Rejected) as error:
        valid_evidence(state, task, driver.directory)
    assert error.value.code == {"digest": "object_corrupt", "missing": "object_missing",
                                "foreign": "evidence_basis", "basis": "evidence_basis"}[damage]


@pytest.mark.parametrize("first_missing", [False, True])
def test_each_command_captures_report_before_next_check(execution_checkpoint, state_backend, monkeypatch,
                                                       first_missing):
    import base64
    import json
    import sys
    from lib import verification
    from lib.state_objects import StateObjects
    driver = execution_checkpoint("pending")
    driver.worktree()
    report_path = driver.root.parent / "command-report-results" / "shared.xml"
    state_backend.artifacts.register(report_path.parent)
    skipped = b'<testsuite tests="8" skipped="8">' + b'<testcase><skipped/></testcase>' * 8 + b'</testsuite>'
    passed = b'<testsuite tests="1" skipped="0"><testcase/></testsuite>'
    sources = {"print('report A')": skipped, "print('report B')": passed}
    original = verification.check_runner.run_command
    def producing_command(command, cwd, timeout):
        output = original(command, cwd, timeout)
        if len(command) > 3 and command[3] in sources:
            if command[3] != "print('report A')" or not first_missing:
                artifacts.write(report_path, sources[command[3]])
        return output
    monkeypatch.setattr(verification.check_runner, "run_command", producing_command)
    checks = [
        {"id": "report-A", "source": "report-contract", "criteria": ["AC-one"],
         "run": {"command": [sys.executable, "-B", "-c", "print('report A')"]},
         "configuration": {"structured_reports": [
             {"format": "pytest-junit", "path": str(report_path), "required": True}]}},
        {"id": "report-B", "source": "report-contract", "criteria": ["AC-one"],
         "run": {"command": [sys.executable, "-B", "-c", "print('report B')",
                             "--junitxml", str(report_path)]}},
    ]
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": checks},
                task_id="TASK-one")
    driver.role("report-author", "executor")
    driver.send("start", {"role_id": "report-author", "paths": ["result.txt", "check.py"]})
    result = driver.run_checks("baseline")
    assert result["outcome"] == ("unavailable" if first_missing else "baseline_recorded")
    record = json.loads(artifacts.read_text(driver.directory / result["log"]))
    objects = StateObjects(driver.directory)
    machines = {output["check_id"]: objects.get(output["summary"]) for output in record["outputs"]}
    first, second = machines["report-A"], machines["report-B"]
    assert first["exit_code"] == second["exit_code"] == 0
    assert first["test_counts"]["skipped"] == (None if first_missing else 8)
    assert first["evidence_complete"] is not first_missing
    assert second["test_counts"]["skipped"] == 0 and second["test_counts"]["passed"] == 1
    assert artifacts.read_bytes(report_path) == passed
    if first_missing:
        assert first["structured_reports"][0]["reference"] is None
        assert first["structured_reports"][0]["error"]
    else:
        primary = objects.get(first["structured_reports"][0]["reference"])
        assert base64.b64decode(primary["content"]) == skipped
        assert primary["path"] == str(report_path)
    primary = objects.get(second["structured_reports"][0]["reference"])
    assert base64.b64decode(primary["content"]) == passed
    assert all("_report_capture" not in output for output in record["outputs"])


@pytest.mark.parametrize("report_kind", ["skips", "missing", "corrupt", "external", "other"])
def test_structured_report_capture_uses_existing_artifact_adapter(execution_checkpoint, state_backend, report_kind):
    import json
    from copy import deepcopy
    from lib import check_evidence
    from lib.state_objects import StateObjects
    driver = execution_checkpoint("verified")
    state_backend.artifacts.register(driver.root)
    report_path = driver.root / "report.xml"
    if report_kind == "external":
        report_path = driver.root.parent / "declared-results" / "report.xml"
        state_backend.artifacts.register(report_path.parent)
    state, task = driver.state, driver.task
    record = json.loads(artifacts.read_text(driver.directory / task["evidence"][-1]["log"]))
    checks = deepcopy(task["checks"])
    report = {"format": "custom-json" if report_kind == "other" else "pytest-junit",
              "path": str(report_path) if report_kind == "external" else "report.xml", "required": True}
    checks[0]["configuration"] = {"structured_reports": [report]}
    output = record["outputs"][0]
    output.update(configuration=checks[0]["configuration"], stdout="full log", stderr="")
    if report_kind in {"skips", "corrupt", "external", "other"}:
        raw = (b'<testsuite tests="8" skipped="8">' + b'<testcase><skipped/></testcase>' * 8
               + b'</testsuite>') if report_kind in {"skips", "external"} else b"non-XML primary bytes"
        artifacts.write(report_path, raw)
    output["_report_capture"] = check_evidence.capture_reports(output)
    aggregate = check_evidence.persist(state, record, checks, driver.directory, "report-fixture")
    objects = StateObjects(driver.directory)
    machine = objects.get(aggregate["checks"][0])
    assert machine["exit_code"] == 0 and machine["outcome"] == "passed"
    assert aggregate["evidence_complete"] is (report_kind in {"skips", "external", "other"})
    assert machine["test_counts"]["skipped"] == (8 if report_kind in {"skips", "external"} else None)
    saved = machine["structured_reports"][0]
    if report_kind in {"missing", "corrupt"}:
        assert saved["error"]
        with pytest.raises(ValueError, match="unavailable"):
            check_evidence.validate(state, record, checks, driver.directory)
    else:
        import base64
        primary = objects.get(saved["reference"])
        assert base64.b64decode(primary["content"]) == raw
        assert primary["path"] == report["path"] and primary["resolved_path"] == str(report_path)
        assert check_evidence.validate(state, record, checks, driver.directory)["evidence_complete"] is True
        if report_kind == "external":
            from lib.common import Rejected
            primary["path"] = "undeclared-substitute.xml"
            machine["structured_reports"][0]["reference"] = objects.put(primary)
            replacement = objects.put(machine)
            record["outputs"][0]["summary"] = replacement
            aggregate["checks"][0] = replacement
            record["summary"] = objects.put(aggregate)
            with pytest.raises(Rejected) as error:
                check_evidence.validate(state, record, checks, driver.directory)
            assert error.value.code == "evidence_basis"


def test_procedure_type_is_explicit_and_deterministic_procedure_belongs_to_explorer(driver):
    from lib import verification
    state = driver.state
    task = state["tasks"]["TASK-one"]
    untyped = {"id": "procedure", "source": "test", "run": {"procedure": "behavioral-name.md"}}
    with pytest.raises(ValueError, match="explicit type"):
        verification.transition(state, task, {"type": "checks_register", "event_id": "register",
            "payload": {"inventory": {"instructions": [], "ci": []}, "additional": [untyped]}}, driver.directory)
    # A filename cannot select ownership: only the explicit kind does.
    from lib.explorer_assignments import execution_kind
    for kind in ("deterministic", "manual", "behavioral"):
        assert execution_kind({**untyped, "execution_kind": kind}) == kind

def test_deterministic_procedure_uses_explorer_and_keeps_current_aggregate(driver):
    driver.worktree()
    driver.send("checks_register", {"inventory": {"instructions": [], "ci": []}, "additional": [
        {"id": "deterministic-procedure", "source": "fixture", "criteria": ["AC-one"],
         "location": "check.py", "execution_kind": "deterministic", "run": {"procedure": "check.py"}}]})
    driver.role("author", "executor")
    driver.send("start", {"role_id": "author", "paths": ["result.txt"]})
    for stage in ("baseline", "independent"):
        if stage == "independent":
            driver.freeze()
        driver.explorer(stage + "-explorer", stage)
        driver.role(stage + "-verifier", "verifier")
        with pytest.raises(ValueError, match="explorer"):
            driver.send("procedure_begin", {"role_id": stage + "-verifier", "stage": stage, "check_id": "deterministic-procedure"})
        driver.send("procedure_begin", {"role_id": stage + "-explorer", "stage": stage, "check_id": "deterministic-procedure"})
        driver.send("procedure_result", {"role_id": stage + "-explorer", "check_id": "deterministic-procedure", "outcome": "passed",
            "steps": ["Synthetic deterministic assertion observation"], "trace": "synthetic-unit-test"})
        result = driver.send("check_run", {"role_id": stage + "-explorer", "stage": stage})
        assert result["outcome"] == ("baseline_recorded" if stage == "baseline" else "passed")
    from lib.verification import valid_evidence
    assert len(valid_evidence(driver.state, driver.task, driver.directory)) == 2
    driver.send("procedure_begin", {"role_id": "independent-explorer", "stage": "independent", "check_id": "deterministic-procedure"})
    with pytest.raises(ValueError, match="latest procedure"):
        valid_evidence(driver.state, driver.task, driver.directory)
    driver.send("procedure_result", {"role_id": "independent-explorer", "check_id": "deterministic-procedure", "outcome": "failed",
        "steps": ["Synthetic failure"], "trace": "synthetic-unit-test"})
    with pytest.raises(ValueError, match="reserve"):
        driver.send("procedure_begin", {"role_id": "independent-explorer", "stage": "independent", "check_id": "deterministic-procedure"})


@pytest.mark.parametrize("kind", ["manual", "behavioral"])
def test_semantic_procedure_requires_task_verifier(kind):
    from lib.explorer_assignments import procedure_role
    task = {"plan": {"id": "TASK-one"}}
    check = {"execution_kind": kind, "run": {"procedure": "eval.md"}}
    state = {"roles": {name: {"kind": name, "task_id": "TASK-one", "status": "active"}
                       for name in ("explorer", "verifier")}}
    with pytest.raises(ValueError, match="task verifier"):
        procedure_role(state, task, "explorer", "independent", check)
    assert procedure_role(state, task, "verifier", "independent", check)["kind"] == "verifier"
