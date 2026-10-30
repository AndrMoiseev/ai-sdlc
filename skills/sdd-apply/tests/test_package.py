from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def test_package_contract():
    assert "disable-model-invocation: false" in (ROOT / "SKILL.md").read_text()
    assert "allow_implicit_invocation: true" in (ROOT / "agents/openai.yaml").read_text()
    for entry in ("execute.py", "test.py"):
        content = (ROOT / "scripts" / entry).read_text()
        assert "# /// script" in content and "sys.dont_write_bytecode = True" in content
        assert (ROOT / "scripts" / (entry + ".lock")).is_file()
    for path in ROOT.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not target.startswith(("http", "#")):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    assert json.loads((ROOT / "schemas/event.schema.json").read_text())["type"] == "object"
    forbidden = {"__pycache__", ".pytest_cache", ".venv", "node_modules"}
    assert not [p for p in ROOT.rglob("*") if p.name in forbidden or p.suffix == ".pyc"]


def test_explorer_execution_instructions_match_role_api():
    from lib.api_help import describe
    registration = describe(event="role_register")
    # Existing API help is the machine contract; linked instructions name the
    # same execution owner and separate evidence consumer.
    serialized = json.dumps(registration)
    assert "explorer" in serialized and "assignment" in serialized
    flow = (ROOT / "flows/execute-parallel.md").read_text()
    verifier = (ROOT / "agents/verifier.md").read_text()
    assert "task explorer" in flow and "raw evidence references" in flow
    assert "machine summary and raw evidence references" in verifier
    assert "procedure_begin/result" in verifier
    conclusion = describe(event="verification_result")
    assert conclusion["choices"]["stage"] == ["independent", "integration"]
    assert conclusion["task_id"] == "TASK-ID"
    final_flow = (ROOT / "flows/finalize.md").read_text()
    assert "accepted" in final_flow and "finalize" in final_flow
    assert "verification_result" in flow and "checks_extend.verification_result" in flow
    assert "`criterion_id`" in verifier and "`check_request`" in verifier
    assert "read_object" in verifier
    assert (ROOT.parent / "sdd-shared/agents/explorer.md").is_file()


def test_prepared_explorer_scenarios_have_consistent_inputs():
    """Validate shipped fixture bytes, not agent behavior or an execution result.

    Real package reads catch omitted/malformed distributed inputs; case combinations
    use those in-memory values and the existing shared JUnit parser, without I/O.
    Only apply/shared are required, including in a relocated installation.
    """
    import ast
    from lib.inputs import spec_modules

    fixture = json.loads((ROOT / "evals/explorer-fixtures.json").read_text(encoding="utf-8"))
    assert fixture["behavioral_result"] == fixture["control"]["behavioral_result"] == "not_run"
    assert fixture["criteria"] == ["AC-explorer-workflow"]
    assert (ROOT / "evals" / fixture["procedure"]).is_file()
    cases = {case["name"]: case for case in fixture["cases"]}
    assert len(cases) == len(fixture["cases"]) == 3
    assert set(cases) == {"ordinary-success", "verbose-failure", "mandatory-skip"}
    common = fixture["common"]
    assert common["metrics"] == {"tokens": None, "cost": None}
    check = common["check"]
    assert check["criteria"] == [common["criterion"]["id"]]
    assert check["execution_kind"] == "deterministic"
    command = check["run"]["command"]
    summary = spec_modules("check_summary")
    assert summary.report_specs(command, check["configuration"]) == [
        {"format": "pytest-junit", "path": "{artifacts}/results.xml", "required": True}]
    evals = json.loads((ROOT / "evals/evals.json").read_text(encoding="utf-8"))["evals"]
    entries = {entry["id"]: entry for entry in evals}
    assert len(entries) == len(evals)
    for case in cases.values():
        entry = entries[case["eval_id"]]
        assert entry["prompt"] == case["prompt"]
        assert entry["files"] == []  # Grader fixture must not be a worker input.
        sources = common["sources"] | case["sources"]
        assert check["location"] in sources and check["location"] in command
        for name, source in sources.items():
            ast.parse(source, filename=name)
        counts = summary.junit_counts(case["sample_report"].encode())
        assert {key: counts[key] for key in ("passed", "failed", "skipped")} == {
            key: case["expected"][key] for key in ("passed", "failed", "skipped")}
        assert counts["collected"] is None and counts["xpassed"] is None
    assert [(cases[name]["expected"]["exit_code"],
             cases[name]["expected"]["criterion_outcome"],
             cases[name]["expected"]["review_eligible"]) for name in
            ("ordinary-success", "verbose-failure", "mandatory-skip")] == [
                (0, "passed", True), (1, "failed", False), (0, "unavailable", False)]
