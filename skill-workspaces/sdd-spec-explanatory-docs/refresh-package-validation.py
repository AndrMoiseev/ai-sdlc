"""Refresh final editorial files and repeat only affected local checks."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone

workspace = Path(__file__).resolve().parent
evidence_path = workspace / "package-validation.json"
data = json.loads(evidence_path.read_text(encoding="utf-8"))
source, copy = Path(data["source"]), Path(data["copy"])
temp = Path(data["temporary_root"])
cwd = temp / "external-cwd"
for name in ["references/explanation.md", "templates/preview-handoff.md", "flows/revise.md", "evals/manual.md"]:
    shutil.copy2(source / name, copy / name)
env = os.environ.copy()
env.update(PYTHONUTF8="1", UV_CACHE_DIR=str(temp / "conductor-cache"), PYTHONPYCACHEPREFIX=str(temp / "conductor-bytecode"))
commands = [
    ("package-copy-contract-final", ["python", str(copy / "scripts/run.py"), "test", "-k", "package_contract"], os.environ.copy()),
]
for label, args, execution_env in commands:
    start = time.monotonic()
    result = subprocess.run(args, cwd=cwd, env=execution_env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (workspace / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (workspace / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    data["commands"].append(dict(label=label, argv=args, cwd=str(cwd), exit_code=result.returncode, seconds=time.monotonic()-start))
    if label == "package-structural-utf8":
        data["structural_records"] = json.loads(result.stdout)
    else:
        data["final_package_contract_passed"] = result.returncode == 0
    print(label, result.returncode)

def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}

data["final_copy_hashes"] = hashes(copy)
data["final_source_matches_copy"] = hashes(source) == data["final_copy_hashes"]
data["final_validation_at_utc"] = datetime.now(timezone.utc).isoformat()
for item in data["relocated_resources"]:
    text = (copy / item["path"]).read_text(encoding="utf-8")
    item["bytes"] = (copy / item["path"]).stat().st_size
    item["author_path_present"] = str(source.parents[1]).lower() in text.lower() or source.parents[1].as_posix().lower() in text.lower()
    if item["path"].startswith("templates/"):
        item["example_links_note"] = "archify/... links are fenced illustrative output links, not bundled resource dependencies"
for label, root in [("source", source), ("copy", copy)]:
    entries = list(root.rglob("*"))
    suspects = [p.relative_to(root).as_posix() for p in entries if p.name in {".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".archify", "timing.json", "grading.json", "benchmark.json", "report.html"} or p.suffix in {".pyc", ".pyo", ".png", ".jpg", ".webp", ".log", ".jsonl"}]
    data["cleanliness"][label] = dict(entries=len(entries), suspects=suspects, hidden_entries=[p.relative_to(root).as_posix() for p in entries if p.name.startswith(".")])
evidence_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("final_source_matches_copy", data["final_source_matches_copy"])
