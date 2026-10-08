"""Package integrity: relocation, explicit invocation and bundled resources."""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---", 2)[1])


def test_explicit_only_entry_and_single_skill():
    metadata = frontmatter(ROOT / "SKILL.md")
    assert metadata["name"] == "sdd-spec"
    assert metadata["disable-model-invocation"] is True
    assert 0 < len(metadata["description"]) <= 1024
    config = yaml.safe_load((ROOT / "agents/openai.yaml").read_text(encoding="utf-8"))
    assert config["policy"]["allow_implicit_invocation"] is False
    assert list(ROOT.rglob("SKILL.md")) == [ROOT / "SKILL.md"]


def test_every_local_markdown_link_resolves_inside_package():
    """A copied package must not depend on the author's repository layout."""
    checked = 0
    for path in ROOT.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        content = path.read_text(encoding="utf-8")
        # Fenced examples describe generated project files, not package links.
        content = re.sub(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", "", content)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", content):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = target.split("#", 1)[0].strip("<>")
            resolved = (path.parent / target).resolve()
            assert resolved.is_relative_to(ROOT.resolve()), (path, target)
            assert resolved.is_file(), (path, target)
            checked += 1
    assert checked >= 30, "The map must actually link its self-contained resources"


def test_required_resources_ship_together():
    files = ["README.md", "pyproject.toml"]
    files += [f"scripts/{name}{suffix}" for name in ("check", "snapshot", "test")
              for suffix in (".py", ".py.lock")]
    files += [f"flows/{name}.md" for name in
              ("explore", "draft", "revise", "review", "user-review", "resume", "plan", "explain")]
    files += [f"templates/{name}.md" for name in
              ("proposal", "spec", "design", "tasks", "state", "review-report", "review-summary", "decisions", "discussion-decisions", "questions", "lens-index", "explanation", "preview-handoff")]
    files += [f"references/{name}.md" for name in
              ("document-format", "discussion", "runtime-setup", "codex", "claude-code", "openspec-origin", "consistency", "reviewer-documents", "reviewer-plan", "editorial-pass", "explanation")]
    for file in files:
        assert (ROOT / file).is_file(), file


def test_runtime_flows_do_not_invoke_openspec():
    paths = [ROOT / "SKILL.md", *sorted((ROOT / "flows").glob("*.md"))]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(?m)^\s*(?:\$\s*)?openspec\s+\w", text), path
        assert not re.search(r"(?<![\w/-])(?:\$|/)openspec-[a-z-]+", text), path


def test_upstream_notice_preserved():
    text = (ROOT / "references/openspec-origin.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2024 OpenSpec Contributors" in text
    assert "Permission is hereby granted, free of charge" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text
