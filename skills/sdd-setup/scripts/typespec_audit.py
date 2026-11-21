"""Inspect the project's TypeSpec compiler after mise tool setup."""
from pathlib import Path
import re
import subprocess

from project_audit import check_mise, mise_reader
from setup_core import read_json


COMPILER = "@typespec/compiler"


def inspect_typespec(project_root, package_dir=None):
    project = Path(project_root).resolve(strict=True)
    package = (project / (package_dir or ".")).resolve(strict=True)
    if not project.is_dir() or not package.is_dir() or not package.is_relative_to(project):
        raise ValueError("Select a package directory inside the project")
    result = {"project_root": str(project), "package_dir": str(package), "package": COMPILER,
              "status": "node_unavailable"}
    mise = check_mise(package)
    execute = mise_reader(package, mise)
    if execute is None:
        result["error"] = mise["evidence"]["error"]
        return result
    try:
        node = Path(execute(["mise", "which", "node"]).decode().strip())
        if not node.is_absolute() or not node.is_file():
            raise ValueError("mise did not resolve a Node executable")

        def run_node(*args):
            return subprocess.run([str(node), *args], cwd=package, check=True, capture_output=True,
                                  encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                  timeout=10).stdout.strip()

        result["node_version"] = run_node("--version")
        result["status"] = "unverified"
        installed = None
        pnp = False
        for directory in (package, *package.parents):
            manifest = directory / "package.json"
            if manifest.is_file() and "declaration" not in result:
                data = read_json(manifest)
                for section in ("devDependencies", "dependencies", "optionalDependencies", "peerDependencies"):
                    if COMPILER in data.get(section, {}):
                        result["declaration"] = {"manifest": str(manifest), "section": section,
                                                 "version": data[section][COMPILER]}
                        break
            local = directory / "node_modules" / COMPILER / "package.json"
            if installed is None and local.is_file():
                installed = local
            pnp = pnp or (directory / ".pnp.cjs").is_file() or (directory / ".pnp.js").is_file()
            if directory == project:
                break
        if pnp:
            result["status"] = "check_with_yarn"
            return result
        if installed is None:
            result["status"] = "restore" if "declaration" in result else "missing"
            return result
        metadata = read_json(installed)
        if metadata.get("name") != COMPILER:
            raise ValueError("Unexpected package in the local TypeSpec compiler directory")
        cli = (installed.parent / metadata["bin"]["tsp"]).resolve(strict=True)
        if not cli.is_relative_to(installed.parent.resolve()):
            raise ValueError("The tsp entry point is outside its installed package")
        version = metadata["version"]
        result["package_version"] = version
        output = run_node(str(cli), "--version")
        if not re.search(r"(?<![\w.+-])v?" + re.escape(version) + r"(?![\w.+-])", output):
            raise ValueError("Local tsp --version did not confirm the installed package version")
        result.update(status="installed" if "declaration" in result else "undeclared", version=version)
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
        result["error"] = (error or str(exc)).strip()
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
    return result
