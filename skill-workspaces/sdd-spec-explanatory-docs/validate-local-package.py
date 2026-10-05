"""Local checks only; no model, agent, or browser execution."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

WORKSPACE = Path(__file__).resolve().parent
REPO = WORKSPACE.parents[1]
SOURCE = REPO / "skills/sdd-spec"
TEMP = Path(tempfile.mkdtemp(prefix="sdd-spec-portability-"))
COPY = TEMP / "installed/sdd-spec"
CWD = TEMP / "external-cwd"
CWD.mkdir()
shutil.copytree(SOURCE, COPY)
EVIDENCE = {"temporary_root": str(TEMP), "source": str(SOURCE), "copy": str(COPY), "commands": []}


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def run(label, args, env=None):
    start = time.monotonic()
    result = subprocess.run([str(a) for a in args], cwd=CWD, env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    (WORKSPACE / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (WORKSPACE / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    EVIDENCE["commands"].append(dict(label=label, argv=[str(a) for a in args], cwd=str(CWD),
                                     exit_code=result.returncode, seconds=time.monotonic()-start))
    return result


def sdd(label, command, *args):
    return run(label, [sys.executable, COPY / "scripts/run.py", command, *args])


def doc(path, kind, records=(), **extra):
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(schema_version=1, document_type=kind, change_id="demo", language="en", **extra)
    body = "---\n" + json.dumps(metadata) + "\n---\n\n"
    for record in records:
        body += "### Record\n\n```yaml\n" + json.dumps(record) + "\n```\n\nDescription.\n\n"
    path.write_text(body, encoding="utf-8")


EVIDENCE["copied_hashes"] = hashes(COPY)
run("package-uv-version", ["uv", "--version"])
sdd("package-copy-cache", "cache-dir")
test_result = sdd("package-copy-tests", "test")
EVIDENCE["copy_tests_passed"] = test_result.returncode == 0
env = os.environ.copy()
env["UV_CACHE_DIR"] = str(TEMP / "conductor-cache")
env["PYTHONPYCACHEPREFIX"] = str(TEMP / "conductor-bytecode")
env["PYTHONUTF8"] = "1"
structural = run("package-structural", ["uv", "run", REPO / "skills/sdd-skill-conductor/scripts/eval_skill.py", COPY, "--json"], env)
try:
    EVIDENCE["structural_records"] = json.loads(structural.stdout)
except ValueError:
    EVIDENCE["structural_records"] = None

# Load new linked resources only from the relocated package.
resources = ["flows/explain.md", "references/explanation.md", "templates/explanation.md", "templates/preview-handoff.md"]
EVIDENCE["relocated_resources"] = []
for relative in resources:
    path = COPY / relative
    text = path.read_text(encoding="utf-8")
    links = []
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if re.match(r"[a-z]+://", target) or target.startswith("#") or "<" in target:
            continue
        resolved = (path.parent / target.split("#")[0]).resolve()
        links.append(dict(target=target, exists=resolved.exists(), inside_copy=resolved.is_relative_to(COPY)))
    EVIDENCE["relocated_resources"].append(dict(path=relative, bytes=path.stat().st_size,
        author_path_present=str(REPO).lower() in text.lower() or REPO.as_posix().lower() in text.lower(), links=links))

# Synthetic fixture mirrors tests/conftest.py. Approval is test data, not user consent.
project = TEMP / "approval-project"
change = project / "sdd/changes/demo"
doc(change / "proposal.md", "proposal")
doc(change / "design.md", "design")
doc(change / "specs/feature/spec.md", "spec", [
    dict(sdd_record="requirement", id="REQ-feature", operation="add"),
    dict(sdd_record="acceptance", id="AC-feature", requirement="REQ-feature", conditions="Input", expected="Output")], capability="feature")
args = ("--project-root", project, "--change", "demo", "--stage", "documents")
before = sdd("approval-snapshot-before", "snapshot", *args)
manifest = json.loads(before.stdout)
approval = dict(sdd_record="user", id="USER-doc-approval", kind="document_approval", scope=dict(stage="document_review"),
                response="Synthetic fixture approval", date="2026-01-01T00:00:00Z", inputs=manifest, status="active")
doc(change / "review/decisions.md", "decisions", [approval])
doc(change / "review/local-fixture/consistency.md", "review", run_id="local-fixture", stage="document_review", lens_id="consistency",
    result="completed_no_findings", started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:01:00Z",
    inputs=manifest, inputs_after=manifest, freshness="current", limitations=[])
normative = {p: (change / p).read_bytes() for p in ["proposal.md", "design.md", "specs/feature/spec.md", "review/decisions.md"]}
(change / "explanation.md").write_text("ARCHIFY_PREVIEW_PENDING:sample\n", encoding="utf-8")
check_before = sdd("approval-check-before", "check", *args)
(change / "archify").mkdir()
(change / "archify/sample.html").write_text("<html><body>Synthetic artifact</body></html>", encoding="utf-8")
(change / "archify/index.md").write_text("Synthetic local exclusion test; no browser validation claimed.\n", encoding="utf-8")
(change / "archify/sample.png").write_bytes(b"synthetic placeholder; not a real PNG")
(change / "explanation.md").write_text("[![Preview](archify/sample.png)](archify/sample.html)\n", encoding="utf-8")
after = sdd("approval-snapshot-after", "snapshot", *args)
check_after = sdd("approval-check-after", "check", *args)
check_a, check_b = json.loads(check_before.stdout), json.loads(check_after.stdout)
EVIDENCE["approval_preservation"] = dict(
    mode="local deterministic mechanism; synthetic artifacts; no route or browser execution",
    manifest_equal=manifest == json.loads(after.stdout),
    normative_bytes_equal=all((change / p).read_bytes() == value for p, value in normative.items()),
    before=check_a["approval_status"], after=check_b["approval_status"],
    check_exit_codes=[check_before.returncode, check_after.returncode],
    approval_status_equal=check_a["approval_status"] == check_b["approval_status"])

suspect_names = {".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", ".archify"}
suspect_suffixes = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".webp", ".log", ".jsonl"}
EVIDENCE["cleanliness"] = {}
for label, root in [("source", SOURCE), ("copy", COPY)]:
    entries = list(root.rglob("*"))  # Includes dotfiles; does not consult Git ignore rules.
    suspects = [p.relative_to(root).as_posix() for p in entries if p.name in suspect_names or p.suffix in suspect_suffixes
                or p.name in {"timing.json", "grading.json", "benchmark.json", "report.html", "stdout.txt", "stderr.txt"}]
    EVIDENCE["cleanliness"][label] = dict(entries=len(entries), suspects=suspects,
        hidden_entries=[p.relative_to(root).as_posix() for p in entries if p.name.startswith(".")])
EVIDENCE["copy_unchanged_after_checks"] = hashes(COPY) == EVIDENCE["copied_hashes"]
current = hashes(SOURCE)
EVIDENCE["source_changed_since_copy"] = [key for key in set(current) | set(EVIDENCE["copied_hashes"])
                                        if current.get(key) != EVIDENCE["copied_hashes"].get(key)]
(WORKSPACE / "package-validation.json").write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in EVIDENCE.items() if k not in {"commands", "copied_hashes", "structural_records"}}, ensure_ascii=False, indent=2))
