# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0", "pytest==8.4.2", "pytest-xdist==3.8.0", "websocket-client==1.8.0"]
# ///
"""Run package tests from any cwd, without writing caches into the package."""
import sys
sys.dont_write_bytecode = True
import os
# xdist workers start fresh interpreters; keep their imports out of the package.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from pathlib import Path
import tempfile
import shutil
import pytest

if __name__ == "__main__":
    # Git for Windows' cmd launcher starts another process for every command.
    # Prefer the real binary in that same installation for this test process.
    git_launcher = shutil.which("git")
    if os.name == "nt" and git_launcher:
        git_launcher = Path(git_launcher)
        git_bin = git_launcher.parent.parent / "mingw64" / "bin"
        if git_launcher.parent.name.lower() == "cmd" and (git_bin / "git.exe").is_file():
            os.environ["PATH"] = str(git_bin) + os.pathsep + os.environ.get("PATH", "")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    args = [str(root / a) if a.startswith("tests/") else a for a in sys.argv[1:]]
    if not any(not a.startswith("-") for a in args):
        args.insert(0, str(root / "tests"))
    temporary = Path(tempfile.mkdtemp(prefix="sdd-apply-tests-")) / "runs"
    # Child-process contracts capture their own streams. Python-level capture
    # avoids redirecting OS file descriptors for every fixture/test phase.
    raise SystemExit(pytest.main(["-c", str(root / "tests/pytest.ini"), "-p", "no:cacheprovider", "--capture=sys", "--basetemp", str(temporary), *args]))
