from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def test_package_contract():
    assert "disable-model-invocation: true" in (ROOT / "SKILL.md").read_text()
    assert "allow_implicit_invocation: false" in (ROOT / "agents/openai.yaml").read_text()
    for entry in ("execute.py", "test.py"):
        content = (ROOT / "scripts" / entry).read_text()
        assert "# /// script" in content and "sys.dont_write_bytecode = True" in content
        assert (ROOT / "scripts" / (entry + ".lock")).is_file()
    for path in ROOT.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not target.startswith(("http", "#")):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    for name in ("event", "state"):
        assert json.loads((ROOT / f"schemas/{name}.schema.json").read_text())["type"] == "object"
    forbidden = {"__pycache__", ".pytest_cache", ".venv", "node_modules"}
    assert not [p for p in ROOT.rglob("*") if p.name in forbidden or p.suffix == ".pyc"]
