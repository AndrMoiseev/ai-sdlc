"""Review proof and a durable debt journal derived from recorded findings."""
from copy import deepcopy


def test_change_context(state, task):
    """Expose original permissions and actual registry changes, not a coverage verdict."""
    from .check_registry import selected
    registry = task.get("check_registry")
    transition = registry.get("transition") if registry else None
    return deepcopy({
        "groups": task["plan"].get("test_changes", []),
        "checks": selected(state, task) if registry else [],
        "transition": transition,
        "confirmed_revision": registry.get("confirmed_revision") if registry else None,
        "assessment": (
            "Compare actual tests and assertions with each approved group, criterion and decision. "
            "Retire only the cancelled structural guarantee; retain behavioral guarantees of mixed tests. "
            "Assess new boundary contracts and interactions by risk. Registry mappings are author claims, "
            "not independent coverage evidence."),
    })


def proven(finding):
    """Validate proof shape; truth and applicability remain host attestations."""
    proof = finding.get("proof")
    return (isinstance(proof, dict)
            and isinstance(proof.get("kind"), str)
            and proof.get("kind") in {"acceptance", "architecture", "project_rule"}
            and all(isinstance(proof.get(key), str) and proof[key].strip()
                    for key in ("source", "violation")))


def technical_debt(state):
    entries = []
    for task_id, task in state["tasks"].items():
        for review in task["reviews"]:
            for index, finding in enumerate(review["findings"], 1):
                if finding["severity"] == "recommendation":
                    entries.append({**finding, "finding_id": f"{task_id}/{review['round_id']}/{index}",
                                    "task_id": task_id, "round_id": review["round_id"]})
    return entries
