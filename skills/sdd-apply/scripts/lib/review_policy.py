"""Review proof and a durable debt journal derived from recorded findings."""


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
