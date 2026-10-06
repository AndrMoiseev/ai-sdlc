import json, re, subprocess, sys
from pathlib import Path

root = Path.cwd()
work = root / "skill-workspaces/sdd-execution-skill/editorial"
source = root / "sdd/changes/sdd-execution-skill"
data = json.loads((work / "edits.json").read_text(encoding="utf-8"))
files = ["research.md", "premortem.md", "proposal.md", "design.md", "specs/sdd-execution/spec.md", "state.md"]
results = []
for name in files:
    original = (source / name).read_text(encoding="utf-8")
    final = original
    for edit in data["edits"] + data["yaml_edits"]:
        if edit["path"] == name:
            assert final.count(edit["old"]) == 1, (name, edit["old"], final.count(edit["old"]))
            final = final.replace(edit["old"], edit["new"], 1)
    target = work / "final" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(final, encoding="utf-8")
    plain = re.sub(r"\A---\n.*?\n---\n", "", final, flags=re.S)
    def block(match):
        value = match.group(0)
        if "sdd_record: acceptance" in value:
            return "\n".join(re.findall(r"^(?:conditions|expected): (.*)$", value, flags=re.M))
        if "sdd_record: question" in value:
            return "\n".join(re.findall(r"^text: (.*)$", value, flags=re.M))
        return ""
    plain = re.sub(r"```.*?```", block, plain, flags=re.S)
    plain = "\n".join(line for line in plain.splitlines() if not line.startswith(("#", "> ", "[")) and "Ответ пользователя, дословно:" not in line)
    prose = work / "prose" / name
    prose.parent.mkdir(parents=True, exist_ok=True)
    prose.write_text(plain, encoding="utf-8")
    proc = subprocess.run([sys.executable, "-B", str(root / ".agents/skills/humanizer-ru/scripts/lint.py"), str(prose)], capture_output=True, text=True, encoding="utf-8")
    results.append({"path": name, "exit_code": proc.returncode, "output": proc.stdout, "stderr": proc.stderr, "before_chars": len(original), "after_chars": len(final)})
(work / "lint-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))

