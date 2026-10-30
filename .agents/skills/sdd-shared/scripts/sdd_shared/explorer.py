"""Data contracts for bounded explorer assignments; no launch, I/O or acceptance."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and bool(value) and all(text(item) for item in value)


def validate_assignment(assignment):
    """Validate shared fields; consumers validate their basis and registered checks."""
    require(isinstance(assignment, dict), "Explorer assignment must be an object")
    require(text(assignment.get("id")), "Explorer assignment requires id")
    kind = assignment.get("kind")
    require(kind in ("research", "checks"), "Explorer kind must be research or checks")
    scope = assignment.get("scope")
    require(isinstance(scope, dict) and set(scope) == {"project", "work", "task"},
            "Explorer scope requires project, work and task (null when absent)")
    require(all(value is None or text(value) for value in scope.values()),
            "Explorer scope values must be identities or null")
    require(isinstance(assignment.get("basis"), dict) and bool(assignment["basis"]),
            "Explorer assignment requires a nonempty basis")
    for field in ("read_scope", "outputs"):
        require(strings(assignment.get(field)), f"Explorer assignment requires {field}")
    require(isinstance(assignment.get("limits"), dict) and bool(assignment["limits"]),
            "Explorer assignment requires explicit limits")
    if kind == "research":
        require(text(assignment.get("question")), "Research requires a question")
        require("check_ids" not in assignment, "Research cannot execute check_ids")
    else:
        require(strings(assignment.get("check_ids")), "Checks require exact check_ids")
        require(len(set(assignment["check_ids"])) == len(assignment["check_ids"]),
                "Checks require unique check_ids")
        require("question" not in assignment, "Checks use check_ids, not a research question")
        require(text(assignment.get("stage")), "Checks require a stage")
        require(type(assignment.get("registry_revision")) is int
                and assignment["registry_revision"] >= 0,
                "Checks require a nonnegative registry_revision")
    return assignment


def check_capabilities(assignment, observations):
    """Gate dependent work on host observations, never on a configured agent name.

    This checks recorded evidence, not the truth of an external host assertion.
    The caller performs probes within existing permissions and retains their trace.
    """
    validate_assignment(assignment)
    require(isinstance(observations, dict), "Capability observations must be an object")
    required = ["launch", "read", "write_artifacts"]
    if assignment["kind"] == "checks":
        required.append("run_command")
    unavailable = []
    for capability in required:
        observation = observations.get(capability)
        if not isinstance(observation, dict):
            reason, trace = "Capability was not observed", None
        elif observation.get("available") is not True:
            reason = observation.get("reason")
            reason = reason if text(reason) else "Capability is unavailable or unconfirmed"
            trace = observation.get("trace")
        elif not text(observation.get("trace")):
            reason, trace = "Capability has no host evidence trace", None
        else:
            continue
        unavailable.append({"capability": capability, "reason": reason, "trace": trace})
    return {"ready": not unavailable, "required": required, "unavailable": unavailable}
