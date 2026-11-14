"""Check six-section Markdown recommendations and rank their effect metadata."""

import re
from pathlib import PurePosixPath

EFFECTS = {"substantial": 2, "local": 1, "not_shown": 0}
STATUSES = {"ready", "needs_check", "observe", "rejected"}
FIELDS = {"id", "status", "card", "source_evidence", "metric_evidence", "effects"}


def validate_card(text):
    """Check the document shape; evidence and design judgments remain with the author."""
    title, sections, fence = None, [], None
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            elif sections and line.strip():
                sections[-1][1] = True
            continue
        if marker:
            fence = marker[1]
            continue
        heading = re.match(r"^ {0,3}##\s+(.+?)\s*#*\s*$", line)
        if heading:
            number = re.match(r"([1-6])\.\s+\S", heading[1])
            if not number:
                raise ValueError("Card needs exactly six numbered level-two sections (1. through 6.)")
            sections.append([int(number[1]), False])
        elif re.match(r"^ {0,3}#\s+\S", line):
            if title is not None or sections:
                raise ValueError("Card needs one title before its six sections")
            title = line.strip()[2:].strip()
        elif sections and line.strip() and not line.lstrip().startswith(("<!--", "#")):
            sections[-1][1] = True
    if not title or [number for number, _ in sections] != list(range(1, 7)):
        raise ValueError("Card needs a title and six numbered sections in order (1. through 6.)")
    if fence or not all(content for _, content in sections):
        raise ValueError("Card has an unclosed fence or an empty section")
    return title


def rank(document, sources, resolve_metric=None, read_card=None):
    cards = document["recommendations"]
    ids, paths, ready, checked = set(), set(), [], []
    for card in cards:
        identity, status = card.get("id"), card.get("status")
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError("Recommendation IDs must be unique nonempty strings")
        ids.add(identity)
        if set(card) - FIELDS:
            raise ValueError(f"{identity}: keep narrative and design fields in the Markdown card, not ranking metadata")
        if status not in STATUSES:
            raise ValueError(f"{identity}: invalid status {status}")
        path = card.get("card")
        if (not isinstance(path, str) or not path or "\\" in path or ":" in path
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                or PurePosixPath(path).suffix != ".md"):
            raise ValueError(f"{identity}: card must be a relative Markdown path inside the report")
        if path in paths:
            raise ValueError(f"{identity}: each recommendation needs its own Markdown card")
        paths.add(path)
        if read_card is None:
            raise ValueError(f"{identity}: provide a Markdown card reader")
        value = {**card, "title": validate_card(read_card(path))}
        evidence, metrics = card.get("source_evidence"), card.get("metric_evidence")
        if not isinstance(evidence, list) or not isinstance(metrics, list):
            raise ValueError(f"{identity}: provide source_evidence and metric_evidence address lists")
        if status == "ready" and (not sources or not evidence):
            raise ValueError(f"{identity}: ready requires inspected sources")
        for reference in evidence:
            if (not isinstance(reference, dict) or set(reference) != {"file", "declaration"}
                    or reference["file"] not in sources or not reference["declaration"]):
                raise ValueError(f"{identity}: source evidence must address a current file and declaration")
        for reference in metrics:
            if not isinstance(reference, dict) or set(reference) != {"path", "key"} or resolve_metric is None:
                raise ValueError(f"{identity}: metric evidence needs a JSONL path, object key and resolver")
            resolve_metric(reference)
        profile = card.get("effects")
        if status == "ready" or profile is not None:
            allowed = set(EFFECTS) if status == "ready" else set(EFFECTS) | {"unknown", "worsening"}
            if (not isinstance(profile, dict) or set(profile) != {"modularity", "regression_risk", "development_speed"}
                    or any(effect not in allowed for effect in profile.values())):
                raise ValueError(f"{identity}: invalid effect profile; unknown or worsening effects cannot be ready")
        if status == "ready":
            if not any(effect != "not_shown" for effect in profile.values()):
                raise ValueError(f"{identity}: no grounded benefit; observe or reject")
            ready.append(value)
        checked.append(value)
    def profile(card):
        return tuple(EFFECTS[card["effects"][key]] for key in ("modularity", "regression_risk", "development_speed"))
    ordered = sorted(ready, key=lambda card: (tuple(-value for value in profile(card)), card["id"]))
    groups, previous = [], None
    for card in ordered:
        current = profile(card)
        if current != previous:
            groups.append([])
            previous = current
        groups[-1].append(card["id"])
    return {"priority_groups": groups,
            "recommendations": ordered + [card for card in checked if card["status"] != "ready"],
            "ordering": "modularity, regression_risk, development_speed; equal profiles remain tied"}


def markdown(document):
    lines = ["# Refactoring directions for sdd-spec", "",
             "| Priority | Recommendation | Modularity | Regression risk | Development speed |",
             "| --- | --- | --- | --- | --- |"]
    priorities = {identity: index for index, group in enumerate(document["priority_groups"], 1) for identity in group}
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    def link(card):
        title = cell(card["title"]).replace("[", "\\[").replace("]", "\\]")
        return f"[{title}](<{card['card']}>)"
    ready = [card for card in document["recommendations"] if card["status"] == "ready"]
    for card in ready[:5]:
        effects = card["effects"]
        lines.append("| " + " | ".join(str(value) for value in (priorities[card["id"]], link(card),
                     effects["modularity"], effects["regression_risk"], effects["development_speed"])) + " |")
    if not ready:
        lines.extend(["", "No evidence-backed directions are ready for sdd-spec discussion."])
    for status in ("needs_check", "observe", "rejected"):
        selected = [card for card in document["recommendations"] if card["status"] == status]
        if selected:
            lines.extend(["", "## " + status.replace("_", " "), ""])
            lines.extend("- " + link(card) for card in selected)
    if len(ready) > 5:
        lines.extend(["", "## Further directions", ""])
        lines.extend("- " + link(card) for card in ready[5:])
    return "\n".join(lines) + "\n"
