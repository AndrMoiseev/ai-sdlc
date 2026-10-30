# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Render simplicity instructions for an already selected reviewer; never select an agent."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "gpt-6-astra": "gpt-6-astra",
    "gpt-6.1-sol": "gpt-6.1-sol",
    "claude-fable-5-1": "claude-fable-5-1",
    "claude-opus-5-5": "claude-opus-5-5",
    "claude-sonnet-5-5": "claude-sonnet-5-5",
    "claude-haiku-5-5": "claude-haiku-5-5",
    "kimi-k3": "kimi-k3",
    "k3": "kimi-k3",
    "k3-256k": "kimi-k3",
    "kimi-k3.1-pro": "kimi-k3",
    "k3.1-pro": "kimi-k3",
    "kimi-k3.1-pro-highspeed": "kimi-k3",
    "k3.1-pro-highspeed": "kimi-k3",
}
FAMILIES = (
    (r"(?:gpt-(?:\d|oss-)[a-z0-9.-]*|o\d+(?:-[a-z0-9.]+)*)", "openai"),
    (r"claude-[a-z0-9]+(?:[.-][a-z0-9]+)*", "claude"),
    (r"(?:kimi-(?:k\d|for-coding)|k\d)[a-z0-9.-]*", "kimi"),
)


def select_profile(model):
    if model is None:
        return None
    if not isinstance(model, str) or not model or model.strip() != model:
        raise ValueError("Model must be a nonempty identifier without surrounding whitespace")
    key = model.lower()
    profile = PROFILES.get(key)
    if profile is None:
        profile = next((name for pattern, name in FAMILIES if re.fullmatch(pattern, key)), None)
    return f"references/simplicity-model-{profile}.md" if profile else None


def render(model=None, root=ROOT):
    profile = select_profile(model)
    instructions = (root / "references/simplicity.md").read_text(encoding="utf-8")
    if profile:
        instructions = instructions.rstrip() + "\n\n" + (root / profile).read_text(encoding="utf-8")
    return {"model": model, "profile": profile, "instructions": instructions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="ID supplied by SDD launch selection or host observation; omit if unknown")
    args = parser.parse_args(argv)
    try:
        print(json.dumps({"ok": True, **render(args.model)}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "code": "simplicity_instructions", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
