"""Review proof and a durable debt journal derived from recorded findings."""
from copy import deepcopy

LENSES = ("verification", "code")


def round_results(task, round_id=None):
    round_id = round_id or task.get("active_review") or (task["reviews"][-1]["round_id"] if task["reviews"] else None)
    return {review["lens_id"]: review for review in task["reviews"] if review["round_id"] == round_id}


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
                    entries.append({**finding, "finding_id": f"{task_id}/{review['round_id']}/{review['lens_id']}/{index}",
                                    "task_id": task_id, "round_id": review["round_id"], "lens_id": review["lens_id"]})
    return entries
