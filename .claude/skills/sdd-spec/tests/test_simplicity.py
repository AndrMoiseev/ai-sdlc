"""Instruction selection is independent of agent/model selection and session storage."""
import json
from pathlib import Path

import pytest
import simplicity


@pytest.mark.parametrize("model,profile", [
    (None, None), ("unknown-model", None), ("my-gpt-6-astra", None),
    ("../../gpt-6-astra", None),
    ("gpt-6-astra", "gpt-6-astra"), ("gpt-6.1-sol", "gpt-6.1-sol"),
    ("GPT-6.1-SOL", "gpt-6.1-sol"), ("gpt-6.1-terra", "openai"), ("o3", "openai"),
    ("claude-fable-5-1", "claude-fable-5-1"), ("claude-opus-5-5", "claude-opus-5-5"),
    ("claude-sonnet-5-5", "claude-sonnet-5-5"), ("claude-haiku-5-5", "claude-haiku-5-5"),
    ("claude-future-model", "claude"), ("kimi-k3", "kimi-k3"),
    ("k3", "kimi-k3"), ("k3-256k", "kimi-k3"), ("kimi-k3.1-pro", "kimi-k3"),
    ("k3.1-pro", "kimi-k3"), ("kimi-k3.1-pro-highspeed", "kimi-k3"),
    ("k3.1-pro-highspeed", "kimi-k3"), ("kimi-k4", "kimi"), ("kimi-for-coding", "kimi"),
])
def test_exact_family_and_unknown_selection(model, profile):
    expected = f"references/simplicity-model-{profile}.md" if profile else None
    assert simplicity.select_profile(model) == expected


@pytest.mark.parametrize("model", ["", " gpt-6-astra", "gpt-6-astra ", [], 42])
def test_invalid_identifiers_are_not_silently_normalized(model):
    with pytest.raises(ValueError):
        simplicity.select_profile(model)


def test_render_reads_only_common_and_one_profile(monkeypatch):
    reads = []
    def read(path, **kwargs):
        reads.append(path.as_posix())
        return path.name
    monkeypatch.setattr(Path, "read_text", read)
    result = simplicity.render("gpt-6.1-sol", root=Path("package"))
    assert reads == ["package/references/simplicity.md", "package/references/simplicity-model-gpt-6.1-sol.md"]
    assert result == {"model": "gpt-6.1-sol", "profile": "references/simplicity-model-gpt-6.1-sol.md",
                      "instructions": "simplicity.md\n\nsimplicity-model-gpt-6.1-sol.md"}
    reads.clear()
    assert simplicity.render(root=Path("package"))["profile"] is None
    assert reads == ["package/references/simplicity.md"]


def test_missing_selected_resource_is_an_error(monkeypatch, capsys):
    def missing(path, **kwargs):
        if path.name == "simplicity.md":
            return "common"
        raise FileNotFoundError("selected profile missing")
    monkeypatch.setattr(Path, "read_text", missing)
    assert simplicity.main(["--model", "gpt-6-astra"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert simplicity.main([]) == 0
    assert json.loads(capsys.readouterr().out)["profile"] is None


def test_shipped_profile_resources_are_complete():
    # The package/resource boundary needs real reads: an in-memory selector cannot
    # detect a missing or empty bundled model file. Read each resource only once.
    profiles = set(simplicity.PROFILES.values()) | {name for _, name in simplicity.FAMILIES}
    for profile in profiles:
        path = simplicity.ROOT / f"references/simplicity-model-{profile}.md"
        assert path.read_text(encoding="utf-8").strip(), path
