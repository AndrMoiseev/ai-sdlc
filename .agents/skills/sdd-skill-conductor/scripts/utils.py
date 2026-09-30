"""Shared utilities for skill-creator scripts."""

import random
from pathlib import Path


def split_evals(
    items: list[dict], holdout: float, seed: int = 42, stratify_key: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Split items into (train, test), optionally stratified by a key.

    Each stratum contributes max(1, int(len * holdout)) items to test, so no
    non-empty stratum is ever missing from the held-out set. Boolean strata are
    ordered truthy-first, which reproduces the historical run_loop.py
    should_trigger split bit-for-bit; other key values are ordered by str() so
    the split is independent of item order in the source file.
    """
    random.seed(seed)
    if stratify_key is None:
        strata = [list(items)]
    else:
        by_key: dict = {}
        for item in items:
            by_key.setdefault(item.get(stratify_key), []).append(item)
        if all(isinstance(k, bool) for k in by_key):
            order = sorted(by_key, reverse=True)
        else:
            order = sorted(by_key, key=str)
        strata = [by_key[k] for k in order]

    train: list[dict] = []
    test: list[dict] = []
    for stratum in strata:
        random.shuffle(stratum)
        n_test = max(1, int(len(stratum) * holdout))
        test += stratum[:n_test]
        train += stratum[n_test:]
    return train, test


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8-sig")
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content


def ensure_implicit_allowed(skill_path: Path, harness: str) -> None:
    """Reject discovery optimization for explicitly invoked skills."""
    import yaml

    _, _, content = parse_skill_md(skill_path)
    frontmatter = yaml.safe_load(content.split("---", 2)[1])
    explicit_only = frontmatter.get("disable-model-invocation") is True
    policy_path = skill_path / "agents" / "openai.yaml"
    if harness == "codex" and policy_path.exists():
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8-sig")) or {}
        explicit_only = explicit_only or policy.get("policy", {}).get("allow_implicit_invocation") is False
    if explicit_only:
        raise ValueError("This skill is explicit-only; run behavioral evals with an explicit invocation, not discovery or description optimization")
