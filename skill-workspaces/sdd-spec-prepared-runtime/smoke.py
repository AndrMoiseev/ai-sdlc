"""Exercise prepared source/installed launchers without uv on PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys


workspace = Path(__file__).resolve().parent
fixture = workspace / "fixture"
change = fixture / "sdd/changes/demo"
(change / "specs/feature").mkdir(parents=True, exist_ok=True)
for filename, kind in [("proposal.md", "proposal"), ("design.md", "design"), ("specs/feature/spec.md", "spec")]:
    frontmatter = f"---\nschema_version: 1\ndocument_type: {kind}\nchange_id: demo\nlanguage: en\n"
    if kind == "spec":
        frontmatter += "capability: feature\n"
    body = "---\n# Fixture\n"
    if kind == "spec":
        body += """
## Feature

```yaml
sdd_record: requirement
id: REQ-feature
operation: add
```

Provide the feature.

### Accept feature

```yaml
sdd_record: acceptance
id: AC-feature
requirement: REQ-feature
conditions: Input is provided
expected: Output is returned
```

Observe the output.
"""
    (change / filename).write_text(frontmatter + body, encoding="utf-8")

environment = os.environ.copy()
environment["PATH"] = ""
environment["UV_OFFLINE"] = "1"
environment["PYTHONDONTWRITEBYTECODE"] = "1"
environment.pop("SDD_SPEC_RUNTIME_DIR", None)
results = []
for root in sys.argv[1:]:
    launcher = Path(root).resolve() / "scripts/run.py"
    for command in ["version", "check", "snapshot"]:
        arguments = [] if command == "version" else ["--project-root", str(fixture), "--change", "demo", "--stage", "documents"]
        result = subprocess.run([sys.executable, "-B", str(launcher), command, *arguments],
                                cwd=workspace, env=environment, text=True, encoding="utf-8", capture_output=True)
        results.append({"launcher": str(launcher), "command": command, "exit_code": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        print(f"{launcher.parent.parent}: {command} -> {result.returncode}")
        if result.returncode:
            print(result.stderr or result.stdout)
(workspace / "smoke-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
raise SystemExit(any(result["exit_code"] for result in results))
