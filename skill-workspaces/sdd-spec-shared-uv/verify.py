"""Exercise the actual shared uv project; write evidence outside skill packages."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


workspace = Path(__file__).resolve().parent
repo = workspace.parents[1]
uv = shutil.which("uv")
assert uv
results = []
fixture = workspace / "fixture"
change = fixture / "sdd/changes/sample-change"
source = repo / "skills/sdd-spec"
for kind, relative in [("proposal", "proposal.md"), ("design", "design.md"),
                       ("spec", "specs/sample-capability/spec.md")]:
    target = change / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((source / "templates" / f"{kind}.md").read_bytes())


def execute(label, command, cwd=workspace, success=True):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    results.append(dict(label=label, command=command, cwd=str(cwd), exit_code=result.returncode,
                        stdout=result.stdout, stderr=result.stderr))
    print(f"{label}: exit {result.returncode}")
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return result


before = hashlib.sha256((repo / "uv.lock").read_bytes()).hexdigest()
for relative in ["skills/sdd-spec", ".agents/skills/sdd-spec", ".claude/skills/sdd-spec"]:
    skill = repo / relative
    command = [uv, "run", "--directory", str(repo), "--locked", "--offline", "python", "-B"]
    result = execute(f"{relative}: interpreter", command + ["-c", "import sys; print(sys.prefix)"], cwd=skill)
    assert Path(result.stdout.strip()).resolve() == (repo / ".venv").resolve()
    for script in ["check", "snapshot"]:
        result = execute(f"{relative}: {script}", command + [str(skill / "scripts" / f"{script}.py"),
                         "--project-root", str(fixture), "--change", "sample-change", "--stage", "documents"])
        payload = json.loads(result.stdout)
        if script == "check":
            assert payload["errors"] == []
    assert not (skill / ".cache").exists()
    assert not (skill / ".venv").exists()
assert not (workspace / ".cache").exists()

# Missing dependencies fail offline; stale declarations do not rewrite the lock.
isolated = workspace / "unprepared"
(isolated / "skills/sdd-spec").mkdir(parents=True, exist_ok=True)
for name in ["pyproject.toml", "uv.lock", "uv.toml"]:
    (isolated / name).write_bytes((repo / name).read_bytes())
declaration = isolated / "skills/sdd-spec/pyproject.toml"
declaration.write_bytes((source / "pyproject.toml").read_bytes())
command = [uv, "run", "--directory", str(isolated), "--locked", "--offline", "python", "-B", "-c", "print('unexpected')"]
execute("missing local dependencies", command, success=False)
declaration.write_text(declaration.read_text(encoding="utf-8").replace("PyYAML==6.0.3", "PyYAML==0.0.0"), encoding="utf-8")
execute("changed dependency declaration", command, success=False)
assert (isolated / "uv.lock").read_bytes() == (repo / "uv.lock").read_bytes()
assert hashlib.sha256((repo / "uv.lock").read_bytes()).hexdigest() == before

bad = []
for collection in ["skills", ".agents/skills", ".claude/skills"]:
    for name in ["sdd-spec", "sdd-skill-conductor"]:
        for path in (repo / collection / name).rglob("*"):
            if path.name in {".venv", "__pycache__", ".pytest_cache", "prepared.json", "uv.lock"} or path.suffix == ".pyc":
                bad.append(str(path))
assert not bad, bad
(workspace / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("Shared interpreter, offline failures, unchanged lock and package cleanliness verified")
