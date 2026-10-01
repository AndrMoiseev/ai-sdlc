"""Run the skill's checks with all generated Python state outside the package."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]


def cache_directory(skill_root: Path) -> Path:
    """Give each source/installed copy its own environment in the user cache."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    if not base.is_absolute():
        raise ValueError("The user cache directory must be an absolute path")
    identity = os.path.normcase(str(skill_root.resolve()))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    cache = (base / "ai-sdlc" / "sdd-spec" / key).resolve()
    package_root = skill_root.resolve()
    boundary = next((p for p in package_root.parents if p.name == "skills"), package_root)
    if cache.is_relative_to(boundary):
        raise ValueError("The user cache directory must be outside the skills directory")
    return cache


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "snapshot", "test", "version", "cache-dir"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        cache = cache_directory(SKILL_ROOT)
    except ValueError as error:
        parser.error(str(error))
    if args.command == "cache-dir":
        print(cache)
        return 0

    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(cache / "venv")
    env["UV_CACHE_DIR"] = str(cache.parent / "uv")
    env["PYTHONPYCACHEPREFIX"] = str(cache / "pycache")
    command = ["uv", "run", "--project", str(SKILL_ROOT), "--locked", "python"]
    if args.command == "test":
        command += ["-m", "pytest", "-o", f"cache_dir={cache / 'pytest'}", str(SKILL_ROOT / "tests")]
    elif args.command == "version":
        command += ["--version"]
    else:
        command += [str(SKILL_ROOT / "scripts" / f"{args.command}.py")]
    command += args.arguments
    try:
        return subprocess.run(command, env=env).returncode
    except FileNotFoundError:
        print("uv is required; install it from https://docs.astral.sh/uv/", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
