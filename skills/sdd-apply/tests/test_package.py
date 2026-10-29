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
    assert "verification_result" in flow and "checks_extend.verification_result" in flow
    assert "`criterion_id`" in verifier and "`check_request`" in verifier
    assert "read_object" in verifier
    assert (ROOT.parent / "sdd-shared/agents/explorer.md").is_file()
