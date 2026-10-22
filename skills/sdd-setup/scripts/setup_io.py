"""File transport and review summaries; persisted plans retain the full contract."""
import json
import os
from pathlib import Path
import re
import stat

from setup_core import decide, digest, pairs, profile_defaults, read_json, require


def read_request(path):
    path = Path(path).resolve(strict=True)
    request = read_json(path)
    require(isinstance(request, dict), "Request must be a JSON object")
    if "inspection_file" not in request and "inspection_sha256" not in request:
        return request
    require(set(request) == {"inspection_file", "inspection_sha256", "roles", "agents"},
            "Use inspection OR inspection_file with inspection_sha256, roles and agents")
    source = request["inspection_file"]
    expected = request["inspection_sha256"]
    require(isinstance(source, str) and bool(source.strip()), "inspection_file must be a file path")
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
            "inspection_sha256 must be the SHA-256 returned by inspect --output")
    source = (path.parent / source).resolve(strict=True)
    require(source.is_file(), "inspection_file must be a JSON file")
    raw = source.read_bytes()
    require(digest(raw) == expected, "Inspection file changed; inspect again and reconcile choices")
    inspection = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs)
    return {"inspection": inspection, "roles": request["roles"], "agents": request["agents"]}


def inspect_summary(result):
    agents = {name: {key: value for key, value in entry.items() if key != "sha256"}
              for name, entry in result["agents"].items()}
    return {key: result[key] for key in ("project_root", "host", "snapshot", "roles")} | {"agents": agents}


def plan_summary(result):
    request = result["request"]
    inspection = request["inspection"]
    by_agent = {}
    for role, name in result["selected_roles"].items():
        by_agent.setdefault(name, []).append(role)
    selected_agents = {}
    for name, roles in by_agent.items():
        entry = inspection["agents"][name]
        defaults = profile_defaults(roles, inspection["host"])
        selected_agents[name] = {"roles": roles, "scope": entry["scope"]}
        for field in ("model", "effort"):
            selected_agents[name][field] = decide(request["agents"][name][field], entry[field],
                                                  defaults[field] if defaults else None, name + "." + field)
        if entry["scope"] == "missing" or any(selected_agents[name][field] != entry[field]
                                               for field in ("model", "effort")):
            selected_agents[name]["scope"] = "project"
    return {"project_root": inspection["project_root"], "host": inspection["host"],
            "plan_id": result["plan_id"], "selected_roles": result["selected_roles"],
            "selected_agents": selected_agents, "warnings": result["warnings"],
            "operations": [{"path": op["path"], "diff": op["diff"]} for op in result["operations"]]}


def output_path(path, project):
    """Accept a new external artifact; reject redirected or package write paths."""
    path = Path(path).absolute()
    resolved = path.resolve()
    require(path.suffix.lower() == ".json", "--output must name a new .json file")
    require(not resolved.is_relative_to(Path(project).resolve()), "--output must be outside the project")
    require(path.parent.is_dir(), "--output parent must be an existing workspace directory")
    for cursor in (path, *path.parents):
        require(cursor.name.lower() != "skills" and not (cursor / "SKILL.md").is_file(),
                "--output must be outside skill packages and collections")
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                f"Symlink or reparse point in output path: {cursor}")
    require(not path.exists(), "--output already exists; choose a new file")
    return path


def save_result(result, path, command):
    summary = inspect_summary(result) if command == "inspect" else plan_summary(result)
    path = output_path(path, summary["project_root"])
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    # Exclusive creation also protects a file appearing after validation.
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"output_file": str(path), "sha256": digest(raw), "summary": summary}
