"""Resolve project SDD roles into launch parameters; never launch an agent."""
import hashlib
import json
import os
from pathlib import Path
import tomllib


ROLES = (
    "sdd-spec.explorer", "sdd-apply.explorer",
    "sdd-spec.document_reviewer", "sdd-spec.plan_reviewer",
    "sdd-spec.editor", "sdd-spec.editorial_reviewer",
    "sdd-apply.executor", "sdd-apply.verifier",
    "sdd-apply.reviewer",
)


class ConfigurationError(ValueError):
    code = "subagent_configuration"


def require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=object_pairs)


def evidence(path, content):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(content).hexdigest()}


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def settings(project):
    path = project / ".sdd/settings.json"
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return {}, None, "settings_missing"
    data = json.loads(content.decode("utf-8-sig"), object_pairs_hook=object_pairs)
    require(isinstance(data, dict), "settings.json must contain an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "settings.json requires schema_version: 1")
    agents = data.get("subagents", {})
    require(isinstance(agents, dict), "subagents must be an object")
    require(not set(agents) - {"roles"}, "Unknown subagents field; supported: roles")
    roles = agents.get("roles", {})
    require(isinstance(roles, dict), "subagents.roles must be an object")
    for role, name in roles.items():
        require(role in ROLES, f"Unknown SDD role: {role}")
        require(nonempty_string(name), f"Agent name for {role} must be a nonempty string")
    return roles, evidence(path, content), "role_unmapped"


def codex_definition(project, name, user_agent_dir):
    """Project scope precedes user scope; identity is the TOML name, not filename."""
    roots = [project / ".codex/agents", user_agent_dir]
    for root in dict.fromkeys(path.resolve() for path in roots):
        matches = []
        try:
            paths = sorted(path for path in root.iterdir() if path.suffix.lower() == ".toml")
        except FileNotFoundError:
            paths = []
        for path in paths:
            content = path.read_bytes()
            try:
                data = tomllib.loads(content.decode("utf-8-sig"))
            except (tomllib.TOMLDecodeError, UnicodeError) as exc:
                # Do not silently select a different definition through a broken catalog.
                raise ConfigurationError(f"Invalid agent TOML {path}: {exc}") from exc
            if data.get("name") == name:
                matches.append((path, content, data))
        require(len(matches) <= 1, f"Duplicate agent name {name!r} in {root}")
        if matches:
            path, content, data = matches[0]
            require(nonempty_string(data.get("description")), f"{path}: description is required")
            require(isinstance(data.get("developer_instructions"), str),
                    f"{path}: developer_instructions is required")
            return data, {**evidence(path, content), "name": name}
    return None, None


def resolve(project_root, role, host, parent_model, parent_effort=None,
            user_agent_dir=None, available_agents=None):
    """Return requested parameters and provenance, not proof of runtime settings.

    Claude's available_agents must come from the actual host catalog. It is not
    reconstructed from disk: managed, CLI and plugin definitions have precedence.
    """
    project = Path(project_root).resolve(strict=True)
    require(project.is_dir(), "project_root must be a directory")
    require(role in ROLES, f"Unknown SDD role: {role}")
    require(host in {"codex", "claude-code"}, f"Unsupported host: {host}")
    require(nonempty_string(parent_model) and parent_model != "inherit",
            "Provide the observed parent's exact model ID, not 'inherit'")
    require(parent_effort is None or nonempty_string(parent_effort), "Invalid parent_effort")
    roles, source, reason = settings(project)
    name = roles.get(role)
    user_root = Path(user_agent_dir) if user_agent_dir is not None else (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "agents")
    result = {"schema_version": 1, "project_root": str(project), "role": role,
              "host": host, "requested_agent": name, "mode": "parent",
              "reason": reason, "settings": source, "definition": None,
              "launch": {}, "warnings": [],
              "resolution": {"parent_model": parent_model, "parent_effort": parent_effort,
                             "user_agent_dir": str(user_root.resolve()) if host == "codex" else None,
                             "available_agents": available_agents if host == "claude-code" else None}}
    if host == "claude-code":
        require(isinstance(available_agents, list)
                and all(nonempty_string(item) for item in available_agents),
                "Claude Code requires available_agents from its actual tool/catalog")
        if name and name in available_agents:
            result.update(mode="native-agent", reason="agent_available",
                          launch={"subagent_type": name})
            return result
        require("general-purpose" in available_agents,
                "No selected agent or general-purpose fallback is available; restore host capability")
        result["launch"] = {"subagent_type": "general-purpose", "model": parent_model}
    else:
        result["launch"] = {"fork_turns": "none", "model": parent_model}
        if parent_effort is not None:
            result["launch"]["reasoning_effort"] = parent_effort
        if name:
            data, definition = codex_definition(project, name, user_root)
            if data is not None:
                model = data.get("model", "inherit")
                effort = data.get("model_reasoning_effort")
                require(nonempty_string(model), "Agent model must be a nonempty string")
                require(effort is None or nonempty_string(effort),
                        "Agent model_reasoning_effort must be a nonempty string")
                # Support future host model IDs/efforts without a stale allowlist.
                result["launch"]["model"] = parent_model if model == "inherit" else model
                if effort is not None:
                    result["launch"]["reasoning_effort"] = effort
                elif result["launch"]["model"] != parent_model:
                    result["launch"].pop("reasoning_effort", None)
                definition["ignored_fields"] = sorted(set(data) - {
                    "name", "description", "model", "model_reasoning_effort"})
                result.update(mode="model-profile", reason="agent_profile", definition=definition)
                result["warnings"].append(
                    "Only model and model_reasoning_effort are applied; agent instructions, "
                    "tools, skills and other settings are not imported. Use the SDD role contract.")
                return result
    if name:
        result["reason"] = "agent_missing"
        result["warnings"].append(f"Agent {name!r} unavailable; using the parent model")
    return result


def launch_identity(selection):
    """Settings that must match before two roles may share a running context."""
    definition = selection.get("definition") or {}
    return {"host": selection["host"], "mode": selection["mode"],
            "launch": selection["launch"],
            "definition_sha256": definition.get("sha256")}


def validate_selection(selection, project_root, role, host):
    """Validate a launch attestation, not the truth of the host's model claim."""
    require(isinstance(selection, dict), "agent_selection must be the resolver result")
    project = Path(project_root).resolve(strict=True)
    roles, source, _ = settings(project)
    require(selection.get("schema_version") == 1 and selection.get("host") == host
            and selection.get("role") == role and selection.get("project_root") == str(project),
            "Agent selection belongs to another role, host or project")
    require(selection.get("settings") == source
            and selection.get("requested_agent") == roles.get(role),
            "Agent settings changed before registration; reconcile the launch before proceeding")
    launch = selection.get("launch")
    require(isinstance(launch, dict), "Agent selection requires launch parameters")
    mode = selection.get("mode")
    if host == "codex":
        require(mode in {"parent", "model-profile"} and launch.get("fork_turns") == "none"
                and nonempty_string(launch.get("model")), "Invalid Codex launch selection")
    else:
        require(mode in {"parent", "native-agent"} and nonempty_string(launch.get("subagent_type")),
                "Invalid Claude Code launch selection")
        if mode == "parent":
            require(launch["subagent_type"] == "general-purpose"
                    and nonempty_string(launch.get("model")), "Invalid parent fallback")
        else:
            require(launch["subagent_type"] == roles.get(role) and "model" not in launch,
                    "Native agent selection must preserve the definition's model")
    definition = selection.get("definition")
    if mode == "model-profile":
        require(isinstance(definition, dict) and nonempty_string(definition.get("path")),
                "Model profile requires definition evidence")
        path = Path(definition["path"])
        require(evidence(path, path.read_bytes())["sha256"] == definition.get("sha256"),
                "Agent definition changed before registration; reconcile the launch")
    resolution = selection.get("resolution")
    require(isinstance(resolution, dict) and set(resolution) == {
        "parent_model", "parent_effort", "user_agent_dir", "available_agents"},
        "Agent selection requires its resolution inputs")
    current = resolve(project, role, host, **resolution)
    require(selection == current,
            "Agent catalog or launch selection changed before registration; reconcile the launch")
