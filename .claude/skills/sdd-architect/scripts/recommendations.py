"""Validate authored judgments and order them lexicographically, without a score."""

EFFECTS = {"substantial": 2, "local": 1, "not_shown": 0}
STATUSES = {"ready", "needs_check", "observe", "rejected"}
FIELDS = ("action", "scenario", "mechanism", "alternative_explanation", "chosen_option", "baseline",
          "expected_effect", "steps", "cost_and_risk", "acceptance", "revisit", "priority_reason")


def rank(document, snapshot):
    cards = document["recommendations"]
    ids, causes, ready = set(), {}, {}
    for card in cards:
        identity, status = card.get("id"), card.get("status")
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError("Recommendation IDs must be unique nonempty strings")
        ids.add(identity)
        if status not in STATUSES:
            raise ValueError(f"{identity}: invalid status {status}")
        if status != "ready":
            required = ("question", "next_action", "decision_if_yes", "decision_if_no") if status == "needs_check" else ("reason", "revisit")
            if any(not card.get(field) for field in required):
                raise ValueError(f"{identity}: {status} needs {', '.join(required)}")
            continue
        if not snapshot.get("revision") or not snapshot.get("source_files"):
            raise ValueError(f"{identity}: ready requires inspected sources at a known revision")
        if document.get("revision") != snapshot["revision"] or document.get("source_state") != snapshot["source_state"]:
            raise ValueError("Recommendation basis does not match the snapshot")
        if any(not card.get(field) for field in FIELDS):
            raise ValueError(f"{identity}: ready requires all recommendation fields: {', '.join(FIELDS)}")
        cause = card.get("cause")
        if not isinstance(cause, str) or not cause:
            raise ValueError(f"{identity}: provide the single cause addressed")
        if cause in causes:
            raise ValueError(f"{identity}: duplicates cause of {causes[cause]}; merge or select one alternative")
        causes[cause] = identity
        if card.get("feasible") is not True or card.get("preserves_required_behavior") is not True:
            raise ValueError(f"{identity}: resolve feasibility and required behavior before ranking")
        if not isinstance(card.get("metric_evidence"), list) or not isinstance(card.get("boundary_change"), bool):
            raise ValueError(f"{identity}: provide metric_evidence and an explicit boundary_change decision")
        if not isinstance(card.get("depends_on"), list) or not all(isinstance(item, str) for item in card["depends_on"]):
            raise ValueError(f"{identity}: depends_on must be an explicit list of recommendation IDs")
        if set(card.get("confidence", {})) != {"observation", "diagnosis", "effect"} or not all(card["confidence"].values()):
            raise ValueError(f"{identity}: distinguish confidence in observation, diagnosis and effect")
        evidence = card.get("source_evidence", [])
        if not evidence:
            raise ValueError(f"{identity}: cite inspected declarations and consumers")
        for reference in evidence:
            if reference.get("file") not in snapshot["source_files"] or not reference.get("declaration") or not reference.get("finding"):
                raise ValueError(f"{identity}: source evidence must identify a snapshot file, declaration and finding")
        profile = card.get("effects", {})
        if set(profile) != {"modularity", "regression_risk", "development_speed"} or any(value not in EFFECTS for value in profile.values()):
            raise ValueError(f"{identity}: unknown or worsening effect needs a decision check before ready ranking")
        if not any(value != "not_shown" for value in profile.values()):
            raise ValueError(f"{identity}: no demonstrated benefit; observe or reject")
        if card.get("boundary_change"):
            boundary = card.get("boundary", {})
            required = {"packages", "responsibility", "public_contract", "allowed_dependencies",
                        "archunit_rule", "import_scope", "forbidden_dependency", "allowed_example"}
            if not required.issubset(boundary) or not all(boundary[key] for key in required):
                raise ValueError(f"{identity}: boundary change needs package, contract and ArchUnit acceptance details")
        ready[identity] = card
    for identity, card in ready.items():
        if any(dependency not in ready for dependency in card.get("depends_on", [])):
            raise ValueError(f"{identity}: prerequisite is absent or not ready")
    def profile(card):
        return tuple(EFFECTS[card["effects"][key]] for key in ("modularity", "regression_risk", "development_speed"))
    ordered = sorted(ready.values(), key=lambda card: (tuple(-value for value in profile(card)), card["id"]))
    groups, previous = [], None
    for card in ordered:
        current = profile(card)
        if current != previous:
            groups.append([])
            previous = current
        groups[-1].append(card["id"])
    execution, remaining = [], list(ordered)
    while remaining:
        available = [card for card in remaining if set(card.get("depends_on", [])) <= set(execution)]
        if not available:
            raise ValueError("Cyclic recommendation prerequisites; revise the decomposition")
        card = available[0]
        execution.append(card["id"])
        remaining.remove(card)
    return {**document, "priority_groups": groups, "execution_order": execution,
            "recommendations": ordered + [card for card in cards if card["status"] != "ready"],
            "ordering": "modularity, regression_risk, development_speed; equal profiles remain tied"}


def markdown(document):
    lines = ["# Refactoring recommendations", "", f"Revision: `{document.get('revision')}`.", "",
             "| Priority | Change | Modularity | Regression risk | Development speed |",
             "| --- | --- | --- | --- | --- |"]
    priorities = {identity: index for index, group in enumerate(document["priority_groups"], 1) for identity in group}
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    ready = [card for card in document["recommendations"] if card["status"] == "ready"]
    for card in ready[:5]:
        effects = card["effects"]
        lines.append("| " + " | ".join(cell(value) for value in (priorities[card["id"]], card["action"],
                     effects["modularity"], effects["regression_risk"], effects["development_speed"])) + " |")
    if not ready:
        lines.extend(["", "No implementation-ready recommendations are established."])
    for card in ready[:5]:
        lines.extend(["", f"## {card['id']}: {card['action']}", ""])
        for field in (*FIELDS[1:], "source_evidence", "metric_evidence", "confidence", "boundary", "depends_on"):
            if field in card:
                lines.extend([f"**{field.replace('_', ' ')}**", "", str(card[field]), ""])
    for status in ("needs_check", "observe", "rejected"):
        selected = [card for card in document["recommendations"] if card["status"] == status]
        if selected:
            lines.extend(["", "## " + status.replace("_", " "), ""])
            for card in selected:
                lines.extend([f"- **{card['id']}**: " + "; ".join(f"{key}: {value}" for key, value in card.items() if key not in {"id", "status"})])
    if len(ready) > 5:
        lines.extend(["", "Further ready recommendations are retained in the JSON: " + ", ".join(card["id"] for card in ready[5:])])
    lines.extend(["", "Execution order (including prerequisites): " + ", ".join(document["execution_order"]), ""])
    return "\n".join(lines)
