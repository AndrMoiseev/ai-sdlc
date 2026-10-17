# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare an external, disposable host probe without launching a model."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path


def prepare(output, host):
    output = Path(output).resolve()
    skill = Path(__file__).resolve().parents[1]
    if output.exists() or output.is_relative_to(skill) or "skills" in {part.casefold() for part in output.parts}:
        raise ValueError("Use a new output directory outside source and installed skill collections")
    project = output / "project"
    settings = project / ".sdd/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"schema_version": 1, "subagents": {"roles": {
        "sdd-spec.document_reviewer": "sdd-probe"}}}, indent=2), encoding="utf-8")
    if host == "codex":
        path = project / ".codex/agents/arithmetic.toml"
        content = ('name = "sdd-probe"\ndescription = "Temporary arithmetic probe"\n'
                   'model = "gpt-6-luna"\nmodel_reasoning_effort = "high"\n'
                   'developer_instructions = "Prefix the answer with NATIVE_DEFINITION_LOADED. Do not use tools."\n')
    else:
        path = project / ".claude/agents/arithmetic.md"
        content = ('---\nname: sdd-probe\ndescription: Temporary arithmetic probe\n'
                   'model: sonnet\neffort: high\ntools: Read\n---\n'
                   'Prefix the answer with NATIVE_DEFINITION_LOADED. Do not use tools.\n')
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    prompt = f'''Run a narrowly scoped SDD subagent selection probe in {project}.
Read and follow the selection contract at {skill / "references/subagents.md"}.
Resolve role sdd-spec.document_reviewer for host {host}, using the actual parent
model metadata and the project's settings. Use the bundled resolver at
{skill / "scripts/resolve_agent.py"} through uv with its lockfile.
For Claude Code, obtain the real available agent catalog from your tool schema;
save its JSON array at {output / "catalog.json"}. Do not infer a catalog from files.
Launch exactly one fresh worker using the resolved parameters. Its assignment is:
"What is 17 + 25? Return the answer. Do not use tools or delegate."
Wait for completion. Return the selection JSON, actual spawn arguments, child identity,
result, and runtime-reported model/effort with their evidence source (null if unavailable).
Do not invent metadata or ask the child which model it is. If any capability, model
or permission is unavailable, report that limitation and stop the dependent operation.
Do not modify the project, definitions or settings. This authorizes only this probe,
not a full SDD workflow. Preserve normal sandbox and permissions.
'''
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output / "evidence.json").write_text(json.dumps({"host": host, "status": "not_run",
        "selection": None, "launch_arguments": None, "launch_trace": None,
        "parent_model": None, "child_model": None, "child_effort": None,
        "child_result": None, "limitations": []}, indent=2), encoding="utf-8")
    return {"project": str(project), "prompt": str(output / "prompt.txt"), "status": "prepared"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude-code"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output_dir, args.host), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "message": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
