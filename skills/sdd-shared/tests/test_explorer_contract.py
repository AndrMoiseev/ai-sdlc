"""Assignment/capability cases use data only; no host launch or filesystem probes."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdd_shared.explorer import check_capabilities, validate_assignment


def assignment(kind="research"):
    result = {"id": "inspect-consumers", "kind": kind,
              "scope": {"project": "project", "work": None, "task": None},
              "basis": {"source": "commit-sha"}, "read_scope": ["skills/sdd-shared"],
              "outputs": ["external-assignment/result.json"], "limits": {"deadline": "run-deadline"}}
    if kind == "research":
        result["question"] = "Which consumers use the role registry?"
    else:
        result.update(check_ids=["shared-suite"], stage="baseline", registry_revision=0)
    return result


def observations():
    return {name: {"available": True, "trace": f"host-probe:{name}", "reason": None}
            for name in ("launch", "read", "write_artifacts", "run_command")}


@pytest.mark.parametrize("kind", ["research", "checks"])
def test_valid_assignment_and_observed_capabilities_do_not_mutate_inputs(kind):
    request, capabilities = assignment(kind), observations()
    before = copy.deepcopy((request, capabilities))
    assert validate_assignment(request) == request
    result = check_capabilities(request, capabilities)
    assert result == {"ready": True, "required": ["launch", "read", "write_artifacts"]
                      + (["run_command"] if kind == "checks" else []), "unavailable": []}
    assert (request, capabilities) == before


@pytest.mark.parametrize("field", ["id", "kind", "scope", "basis", "read_scope", "outputs", "limits", "question"])
def test_incomplete_research_assignment_is_rejected(field):
    request = assignment()
    del request[field]
    with pytest.raises(ValueError):
        validate_assignment(request)


@pytest.mark.parametrize("field,value", [("check_ids", []), ("check_ids", ["same", "same"]),
                                          ("stage", ""), ("registry_revision", True),
                                          ("registry_revision", -1), ("question", "run something")])
def test_invalid_check_assignment_is_rejected(field, value):
    request = assignment("checks")
    request[field] = value
    with pytest.raises(ValueError):
        validate_assignment(request)


def test_research_does_not_authorize_checks_and_null_scope_needs_no_task():
    request = assignment()
    request["scope"] = {"project": None, "work": None, "task": None}
    assert validate_assignment(request)["scope"]["task"] is None
    request["check_ids"] = ["unregistered"]
    with pytest.raises(ValueError, match="Research cannot execute"):
        validate_assignment(request)


@pytest.mark.parametrize("capability", ["launch", "read", "write_artifacts", "run_command"])
@pytest.mark.parametrize("available", [False, None, "true", 1])
def test_missing_capability_blocks_dependent_checks_and_preserves_reason(capability, available):
    capabilities = observations()
    capabilities[capability] = {"available": available, "trace": "host:denied", "reason": "permission denied"}
    request = assignment("checks")
    request["agent_selection"] = {"requested_agent": "explorer"}
    result = check_capabilities(request, capabilities)
    assert result["ready"] is False
    assert result["unavailable"] == [{"capability": capability, "reason": "permission denied", "trace": "host:denied"}]


@pytest.mark.parametrize("value", [None, {}, {"available": True}, {"available": True, "trace": ""}])
def test_agent_name_or_untraced_assertion_does_not_prove_capability(value):
    capabilities = observations()
    capabilities["read"] = value
    result = check_capabilities(assignment(), capabilities)
    assert result["ready"] is False
    assert result["unavailable"][0]["capability"] == "read"
    assert result["unavailable"][0]["reason"]


def test_research_requires_no_command_capability_but_checks_do():
    capabilities = observations()
    del capabilities["run_command"]
    assert check_capabilities(assignment(), capabilities)["ready"] is True
    assert check_capabilities(assignment("checks"), capabilities)["unavailable"] == [
        {"capability": "run_command", "reason": "Capability was not observed", "trace": None}]
