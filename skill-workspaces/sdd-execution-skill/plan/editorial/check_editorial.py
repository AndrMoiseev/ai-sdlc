# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import sys
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
CHANGE = ROOT / "sdd/changes/sdd-execution-skill"
OUT = Path(__file__).resolve().parent
files = {"tasks": CHANGE / "tasks.md", "state": CHANGE / "state.md", "summary": CHANGE / "review/summary.md"}

def prose(text):
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"^>.*$", "", text, flags=re.M)
    return re.sub(r"```.*?```", "", text, flags=re.S)

def select(text, names):
    sections = re.split(r"(?=^## )", text, flags=re.M)
    return "\n".join(part for part in sections if part.splitlines()[0].removeprefix("## ") in names)

def protected(text):
    front = re.match(r"\A---\n.*?\n---\n", text, re.S)
    result = [front.group(0)] if front else []
    for block in re.findall(r"```yaml\n(.*?)\n```", text, re.S):
        result.append(re.sub(r'^(\s*(?:test_description|setup_required):).*$', r'\1 <editable>', block, flags=re.M))
        for value in re.findall(r'^\s*setup_required: (.+)$', block, re.M):
            for command in re.findall(r'uv run --locked --script [^;]+? -q', json.loads(value)):
                result.append(command)
    return result

extractions = []
task_text = files["tasks"].read_text(encoding="utf-8")
for name, file in files.items():
    text = file.read_text(encoding="utf-8")
    if name == "state":
        text = select(text, {"Следующий шаг", "Предложения", "Проверки и ограничения", "Продолжение", "Планирование без повторного ревью"})
    if name == "summary":
        text = text[text.index("Оба отчёта остаются устаревшими"):]
    extracted = prose(text)
    if name == "tasks":
        for block in re.findall(r"```yaml\n(.*?)\n```", text, re.S):
            task_id = re.search(r"^id: (.+)$", block, re.M).group(1)
            for field, value in re.findall(r"^\s*(test_description|setup_required): (.+)$", block, re.M):
                extracted += "\n\n" + task_id + " / " + field + "\n" + json.loads(value)
    extraction_path = OUT / (name + "-prose.md")
    extraction_path.write_text(extracted, encoding="utf-8")
    extractions.append(str(extraction_path.relative_to(ROOT)))

before = (OUT / "tasks-before.md").read_text(encoding="utf-8")
if protected(before) != protected(task_text):
    raise SystemExit("Protected task data changed during editorial pass")
actual = re.findall(r"^id: (AC-[a-z0-9-]+)$", (CHANGE / "specs/sdd-execution/spec.md").read_text(encoding="utf-8"), re.M)
covered = [ac.strip() for row in re.findall(r"^covers: \[(.*)\]$", task_text, re.M) for ac in row.split(",")]
if sorted(actual) != sorted(covered) or len(set(covered)) != len(covered):
    raise SystemExit("AC coverage mismatch")
lint_script = ROOT / ".agents/skills/humanizer-ru/scripts/lint.py"
combined = "\n\n".join((ROOT / path).read_text(encoding="utf-8") for path in extractions)
(OUT / "final-prose.md").write_text(combined, encoding="utf-8")
result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(lint_script), str(OUT / "final-prose.md")], capture_output=True, text=True, encoding="utf-8")
(OUT / "lint.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
report = {"extractions": extractions, "coverage": len(covered), "unique_coverage": len(set(covered)), "protected_task_data": "unchanged", "lint_exit": result.returncode,
          "hashes": {str(path.relative_to(CHANGE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files.values()}}
(OUT / "editorial-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
print(result.stdout[-1600:])
sys.exit(result.returncode)
