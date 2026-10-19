"""Deterministic project setup. No model calls, global writes or permission changes."""
import copy
import difflib
import hashlib
from shared import locate, load
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import tomlkit
from ruamel.yaml import YAML

PACKAGE = Path(__file__).resolve().parents[1]
DESCRIPTION = "SDD worker for an explicitly assigned specification or implementation role."
INSTRUCTIONS = (
    "Follow the SDD role contract, task scope, source paths and output format supplied "
    "by the parent. Read the referenced role instructions before acting. Work only on "
    "the assigned task. For review and verification, report evidence and findings; "
    "change implementation files only when the assigned role explicitly authorizes it. "
    "Report missing inputs and failed checks accurately."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def identity(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def read_bytes(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def text_value(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and not any(ord(c) < 32 for c in value)


def shared_contract(sdd_spec=None, sdd_shared=None):
    root = locate(explicit=sdd_shared, legacy=sdd_spec)
    return load(root, "subagents"), root / "scripts/sdd_shared/subagents.py"


def safe_target(project, relative):
    """Reject redirected write paths, including Windows junctions, before mkdir."""
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts, "Invalid project write path")
    path = project / relative
    require(path.resolve().is_relative_to(project), f"Write escapes project: {path}")
    cursor = path
    while cursor != project:
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            pass
        else:
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                    f"Symlink or reparse point in write path: {cursor}")
        cursor = cursor.parent
    return path


def yaml_codec():
    codec = YAML(typ="rt")
    codec.allow_duplicate_keys = False
    codec.preserve_quotes = True
    return codec


def parse_agent(raw, host, path):
    text = raw.decode("utf-8-sig")
    if host == "codex":
        data = tomlkit.parse(text)
        body = None
    else:
        match = re.match(r"\A---\r?\n(.*?)^---[ \t]*(?:\r?\n|$)(.*)\Z", text, re.M | re.S)
        require(match is not None, f"Invalid agent frontmatter: {path}")
        data = yaml_codec().load(match[1])
        body = match[2]
    require(isinstance(data, dict), f"Agent must contain a mapping: {path}")
    require(text_value(data.get("name")) and text_value(data.get("description")),
            f"Agent requires name and description: {path}")
    if host == "codex":
        require(isinstance(data.get("developer_instructions"), str), f"Missing developer_instructions: {path}")
    else:
        require(bool(body.strip()), f"Missing agent instructions: {path}")
    for field in ("model", "model_reasoning_effort" if host == "codex" else "effort"):
        require(field not in data or text_value(data[field]), f"Invalid {field}: {path}")
    return data, body


def scan_agents(root, host, scope):
    records = {}
    evidence = {}
    try:
        children = list(root.iterdir())
    except FileNotFoundError:
        return records, evidence
    # Claude discovers subfolders; Codex's SDD profile adapter scans direct TOML files.
    paths = sorted(root.rglob("*.md")) if host == "claude-code" else sorted(p for p in children if p.suffix.lower() == ".toml")
    for path in paths:
        raw = path.read_bytes()
        evidence[str(path.resolve())] = digest(raw)
        data, _ = parse_agent(raw, host, path)
        name = data["name"]
        require(name not in records, f"Duplicate agent name {name!r} in {root}")
        records[name] = {"name": name, "scope": scope, "path": str(path.absolute()),
                         "model": data.get("model"),
                         "effort": data.get("model_reasoning_effort" if host == "codex" else "effort"),
                         "sha256": digest(raw)}
    return records, evidence


def inspect_project(project_root, host, sdd_spec=None, user_agent_dir=None, available_agents=None, names=None, sdd_shared=None):
    require(host in ("codex", "claude-code"), "Supported hosts: codex, claude-code")
    project = Path(project_root).resolve(strict=True)
    require(project.is_dir(), "project_root must be a directory")
    shared, contract_path = shared_contract(sdd_spec, sdd_shared)
    defaults_path = PACKAGE / "assets/defaults.json"
    presets = read_json(defaults_path)["roles"]
    require(set(presets) == set(shared.ROLES), "sdd-setup defaults and sdd-shared roles differ; update both skills")
    roles, settings_evidence, _ = shared.settings(project)
    names = sorted(set(names or []))
    require(all(text_value(name) for name in names), "names must contain agent names")
    if host == "claude-code":
        require(isinstance(available_agents, list) and all(text_value(n) for n in available_agents),
                "Claude Code needs available_agents from the current host catalog, not a disk-derived list")
        available_agents = sorted(set(available_agents))
    else:
        require(available_agents is None, "available_agents is only supported for Claude Code")
    host_dir = ".codex" if host == "codex" else ".claude"
    user_root = Path(user_agent_dir).resolve() if user_agent_dir else (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "agents"
        if host == "codex" else Path.home() / ".claude/agents")
    local, local_evidence = scan_agents(project / host_dir / "agents", host, "project")
    personal, user_evidence = scan_agents(user_root, host, "user")
    catalog = {**personal, **local}
    requested_names = set(names) | set(roles.values()) | {p["agent"] for p in presets.values()}
    agents = {}
    for name in sorted(requested_names):
        entry = copy.deepcopy(catalog.get(name, {"name": name, "scope": "missing", "path": None,
                                               "model": None, "effort": None, "sha256": None}))
        if host == "claude-code":
            entry["available"] = name in available_agents
            if entry["scope"] == "missing" and entry["available"]:
                entry["scope"] = "native"
        agents[name] = entry
    result = {
        "schema_version": 1, "project_root": str(project), "host": host,
        "inputs": {"project_root": str(project), "host": host, "sdd_shared": str(contract_path.parents[2]),
                   "user_agent_dir": str(user_root.resolve()), "available_agents": available_agents, "names": names},
        "roles": [{"role": role, "present": role in roles, "current": roles.get(role),
                   "default": presets[role]["agent"], "profile_default": presets[role][host]}
                  for role in shared.ROLES],
        "agents": agents,
        "evidence": {"settings": settings_evidence, "agents": {**user_evidence, **local_evidence},
                     "contract": digest(contract_path.read_bytes()), "defaults": digest(defaults_path.read_bytes())},
    }
    result["snapshot"] = identity(result)
    return result


def decide(choice, current, default, label):
    require(isinstance(choice, dict), f"Explicit decision required for {label}")
    action = choice.get("action")
    require(action in ("keep", "default", "set"), f"Invalid decision for {label}")
    require(set(choice) == ({"action", "value"} if action == "set" else {"action"}), f"Unexpected fields for {label}")
    value = current if action == "keep" else default if action == "default" else choice["value"]
    require(value is None or text_value(value), f"Invalid value for {label}")
    return value


def profile_defaults(roles, host):
    presets = read_json(PACKAGE / "assets/defaults.json")["roles"]
    values = [presets[r][host] for r in roles]
    # A deliberately shared agent needs one profile; conflicting per-role defaults
    # are not resolved by incidental ordering.
    return values[0] if all(v == values[0] for v in values) else None


def render_agent(raw, host, name, model, effort):
    if raw is None:
        data = tomlkit.document() if host == "codex" else yaml_codec().load("{}")
        data["name"] = name
        data["description"] = DESCRIPTION
        body = "\n" + INSTRUCTIONS + "\n"
        if host == "codex":
            data["developer_instructions"] = INSTRUCTIONS
    else:
        data, body = parse_agent(raw, host, name)
    if model is None or model == "inherit":
        if host == "codex":
            data.pop("model", None)
        else:
            data["model"] = "inherit"
    else:
        data["model"] = model
    field = "model_reasoning_effort" if host == "codex" else "effort"
    if effort is None:
        data.pop(field, None)
    else:
        data[field] = effort
    if host == "codex":
        return tomlkit.dumps(data)
    stream = io.StringIO()
    yaml_codec().dump(data, stream)
    return "---\n" + stream.getvalue() + "---\n" + body


def make_plan(request):
    require(isinstance(request, dict) and set(request) == {"inspection", "roles", "agents"},
            "Request requires inspection, roles and agents only")
    previous = request["inspection"]
    require(isinstance(previous, dict) and isinstance(previous.get("inputs"), dict), "Provide the inspect result")
    current = inspect_project(**previous["inputs"])
    require(previous == current, "Project or agent catalog changed; inspect again and reconcile choices")
    choices = request["roles"]
    require(isinstance(choices, dict) and set(choices) == {r["role"] for r in current["roles"]},
            "Decide every role exactly once")
    selected = {}
    by_agent = {}
    for row in current["roles"]:
        require(row["present"] or choices[row["role"]] != {"action": "keep"},
                f"{row['role']} is missing; accept its default or choose a value")
        name = decide(choices[row["role"]], row["current"], row["default"], row["role"])
        if name is not None:
            selected[row["role"]] = name
            by_agent.setdefault(name, []).append(row["role"])
    agent_choices = request["agents"]
    require(isinstance(agent_choices, dict) and set(agent_choices) == set(by_agent),
            "Decide model and effort for every distinct selected agent")
    project = Path(current["project_root"])
    host = current["host"]
    operations = []
    warnings = []

    def operation(relative, content):
        target = safe_target(project, relative)
        before = read_bytes(target)
        after = content.encode("utf-8")
        if before == after:
            return
        operations.append({"path": Path(relative).as_posix(), "before_sha256": digest(before) if before is not None else None,
                           "before": before.decode("utf-8-sig") if before is not None else None,
                           "after": content, "after_sha256": digest(after),
                           "diff": "".join(difflib.unified_diff(
                               (before.decode("utf-8-sig") if before is not None else "").splitlines(True),
                               content.splitlines(True), fromfile=str(relative), tofile=str(relative)))})

    for name, roles in sorted(by_agent.items()):
        require(name in current["agents"], f"Inspect again with --names {name} before selecting a new name")
        entry = current["agents"][name]
        decision = agent_choices[name]
        require(isinstance(decision, dict) and set(decision) == {"model", "effort"}, f"Decide model and effort for {name}")
        defaults = profile_defaults(roles, host)
        for field in ("model", "effort"):
            choice = decision[field]
            require(isinstance(choice, dict), f"Decision missing for {name}.{field}")
            require(choice.get("action") != "default" or defaults is not None,
                    f"Roles sharing {name} have different presets; choose one explicit model and effort")
            require(entry["scope"] != "missing" or choice.get("action") != "keep",
                    f"{name}.{field} is missing; accept its default or choose a value")
            require(entry["scope"] == "native" or entry[field] is not None or choice.get("action") != "keep",
                    f"{name}.{field} is unset; accept its default or explicitly choose inheritance with null")
        if entry["scope"] == "native":
            require(all(decision[f] == {"action": "keep"} for f in ("model", "effort")),
                    f"{name} is host-managed: keep it or choose a new project agent name")
            warnings.append(f"{name}: native definition retained; model/effort unavailable from the name-only host catalog")
            continue
        model = decide(decision["model"], entry["model"], defaults["model"] if defaults else None, name + ".model")
        effort = decide(decision["effort"], entry["effort"], defaults["effort"] if defaults else None, name + ".effort")
        if entry["scope"] != "missing" and model == entry["model"] and effort == entry["effort"]:
            continue  # Preserve bytes, formatting, inherited fields and global scope on keep.
        if host == "claude-code":
            require(effort is None or effort in {"low", "medium", "high", "xhigh", "max"},
                    "Unsupported Claude effort; choose low, medium, high, xhigh, max or null")
        else:
            require(effort is None or effort in {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"},
                    "Unsupported Codex effort")
        if entry["scope"] == "project":
            relative = Path(entry["path"]).relative_to(project)
        else:
            require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name) is not None,
                    f"New project agent names must match [a-z][a-z0-9-] (max 64): {name}")
            suffix = ".toml" if host == "codex" else ".md"
            relative = Path(".codex" if host == "codex" else ".claude") / "agents" / (name + suffix)
            require(read_bytes(safe_target(project, relative)) is None, f"Agent filename already occupied: {relative}")
        raw = Path(entry["path"]).read_bytes() if entry["path"] else None
        operation(relative, render_agent(raw, host, name, model, effort))
        if entry["scope"] == "user":
            warnings.append(f"{name}: create a project override; personal definition remains unchanged")
    settings_path = safe_target(project, ".sdd/settings.json")
    raw_settings = read_bytes(settings_path)
    settings = read_json(settings_path) if raw_settings is not None else {"schema_version": 1}
    original = copy.deepcopy(settings)
    settings.setdefault("subagents", {})["roles"] = selected
    if raw_settings is None or settings != original:
        operation(".sdd/settings.json", json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    if host == "claude-code":
        warnings.append("Verify selected names and their effective definitions in the live host catalog after writing. Reload/restart if needed; disk discovery does not prove native precedence or model availability.")
    else:
        warnings.append("SDD imports only model and model_reasoning_effort from Codex profiles; task instructions come from the SDD role contract.")
    warnings.append("Presets are recommendations, not proof of model access or model/effort compatibility. No model was launched.")
    result = {"schema_version": 1, "request": copy.deepcopy(request), "operations": operations,
              "selected_roles": selected, "warnings": warnings}
    result["plan_id"] = identity(result)
    return result


def replace_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=".sdd-setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(staged, stat.S_IMODE(path.stat().st_mode))
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def apply_plan(plan):
    require(isinstance(plan, dict) and isinstance(plan.get("request"), dict), "Provide the plan result, not the CLI envelope")
    verified = make_plan(plan["request"])
    require(verified == plan, "Plan changed or was edited; regenerate the plan")
    project = Path(plan["request"]["inspection"]["project_root"])
    if not plan["operations"]:
        return {"changed": [], "plan_id": plan["plan_id"], "warnings": plan["warnings"]}
    lock = safe_target(project, ".sdd/.setup.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError("Another setup owns .sdd/.setup.lock; inspect the owner before removing a stale lock") from exc
    completed = []
    try:
        with handle:
            handle.write(json.dumps({"pid": os.getpid(), "plan_id": plan["plan_id"]}))
        require(make_plan(plan["request"]) == plan, "Inputs changed while acquiring setup lock")
        for operation in plan["operations"]:
            path = safe_target(project, operation["path"])
            before = read_bytes(path)
            require((digest(before) if before is not None else None) == operation["before_sha256"],
                    f"File changed before write: {path}")
            replace_file(path, operation["after"].encode("utf-8"))
            completed.append((path, before, operation["after_sha256"]))
        for path, _, expected in completed:
            require(digest(path.read_bytes()) == expected, f"Post-write check failed: {path}")
    except Exception as exc:
        conflicts = []
        for path, before, written_hash in reversed(completed):
            try:
                now = read_bytes(path)
                require(now is not None and digest(now) == written_hash, "Concurrent edit")
                if before is None:
                    path.unlink()
                else:
                    replace_file(path, before)
            except Exception:
                conflicts.append(str(path))
        suffix = f"; rollback needs manual reconciliation: {conflicts}" if conflicts else "; completed file writes rolled back"
        raise ValueError(str(exc) + suffix) from exc
    finally:
        lock.unlink()
    return {"changed": [op["path"] for op in plan["operations"]], "plan_id": plan["plan_id"], "warnings": plan["warnings"]}
