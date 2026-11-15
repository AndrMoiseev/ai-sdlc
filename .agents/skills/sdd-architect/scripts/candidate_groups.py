"""Pure preliminary grouping and investigation order; no source diagnosis or I/O."""

from collections import defaultdict
from itertools import combinations

from graph import module_for
from measurements import CATALOG, key_text, record_key


SELECTION_NAMES = ("rankings", "signals", "candidate-groups", "investigation-queue")
EVIDENCE_FAMILIES = {"cycle": "dependency_structure", "boundary": "dependency_structure",
                     "coupling": "change_patterns", "hotspot": "change_patterns",
                     "complexity": "code_risk", "coverage": "code_risk", "crap": "code_risk", "shape": "code_risk"}


def selection_reference(name, field, identity):
    return {"path": f"selections/{name}.jsonl", "key": {field: identity}}


def prepare_candidate_groups(config, rows, outcomes, signals, policy):
    """Keep all groups and omissions; merge exact complete scopes, never overlaps."""
    limit = policy["investigation"]["candidate_group_limit"]
    unique = {}
    for signal in signals:
        signal = {**signal, "references": sorted(signal["references"], key=key_text)}
        unique[key_text(signal)] = signal
    signals = [{**unique[key], "signal": f"signal-{index:04d}"}
               for index, key in enumerate(sorted(unique), 1)]
    measurements = {(spec["path"], key_text(record_key(name, row))): (name, row)
                    for name, spec in CATALOG.items() if outcomes[name]["status"] == "complete"
                    for row in rows[name]}
    sources = {row["file"]: row for row in rows["source-files/file"]}
    mappings = {row["class"]: row["file"] for row in rows["class-files/class"]}
    packages, modules = defaultdict(set), defaultdict(set)
    module_error = None
    for path, source in sources.items():
        packages[source["package"]].add(path)
        try:
            owner = module_for(source["package"], config.get("modules", {}))
            if owner is not None:
                modules[owner].add(path)
        except ValueError as error:
            module_error = str(error)
    if module_error:
        modules.clear()

    def objects(identifier, row):
        level = identifier.split("/")[1]
        if "file" in row:
            return {row["file"]}, []
        if level == "file-pair":
            return {row["left"], row["right"]}, []
        members = row.get("members", [row.get("node", row.get(level))])
        files, unresolved = set(), []
        for member in members:
            known = ({mappings[member]} if member in mappings else set()) if level == "class" else (
                packages.get(member, set()) if level == "package" else modules.get(member, set()))
            if known:
                files.update(known)
            else:
                unresolved.append({"level": level, "object": member})
        return files, sorted(unresolved, key=key_text)

    scopes, provisional = {}, {}
    for signal in signals:
        files, unresolved = set(), {}
        for ref in signal["references"]:
            identifier, row = measurements[(ref["path"], key_text(ref["key"]))]
            found, missing = objects(identifier, row)
            files.update(found)
            for value in missing:
                unresolved[key_text(value)] = value
        scope = {"files": sorted(files)}
        if unresolved:
            # An identical mapped subset does not identify a partially mapped group.
            scope["unresolved_objects"] = [unresolved[key] for key in sorted(unresolved)]
            scope["measurement_objects"] = signal["references"]
        scope_key = key_text(scope)
        group = provisional.setdefault(scope_key, {"scope": scope, "seed_signals": []})
        group["seed_signals"].append(signal["signal"])
        scopes[signal["signal"]] = scope

    groups = [{"group": f"group-{index:04d}", **provisional[key]}
              for index, key in enumerate(sorted(provisional), 1)]
    by_signal = {signal["signal"]: signal for signal in signals}
    by_group = {group["group"]: group for group in groups}
    membership = defaultdict(set)
    for group in groups:
        for path in group["scope"]["files"]:
            membership[path].add(group["group"])

    # Attach contained signals as context without merging their groups. Use an
    # inverted file index so disjoint areas do not require pairwise scans.
    attached = {group["group"]: set(group["seed_signals"]) for group in groups}
    for identity, scope in scopes.items():
        if scope.get("unresolved_objects") or not scope["files"]:
            continue
        containing = set.intersection(*(membership[path] for path in scope["files"]))
        for group_id in containing:
            if not by_group[group_id]["scope"].get("unresolved_objects"):
                attached[group_id].add(identity)
    intersections = defaultdict(set)
    for path, group_ids in sorted(membership.items()):
        for left, right in combinations(sorted(group_ids), 2):
            intersections[left, right].add(path)
    overlaps = defaultdict(list)
    for (left, right), files in sorted(intersections.items()):
        overlaps[left].append({"group": right, "shared_files": sorted(files)})
        overlaps[right].append({"group": left, "shared_files": sorted(files)})

    for group in groups:
        families = {}
        for identity in sorted(attached[group["group"]]):
            signal = by_signal[identity]
            family = families.setdefault(EVIDENCE_FAMILIES[signal["family"]], {"points": 0, "signals": []})
            # Cap related observations at one contribution; raw metric magnitudes
            # and diagnostic evidence weights never become comparable severity.
            family["points"] = max(family["points"], policy["investigation"]["family_points"][signal["suitability"]])
            family["signals"].append(selection_reference("signals", "signal", identity))
        group["evidence_families"] = dict(sorted(families.items()))
        group["investigation_score"] = sum(family["points"] for family in families.values())
        missing = sorted(set(group["scope"]["files"]) - sources.keys())
        group["source_available"] = bool(group["scope"]["files"]) and not missing and not group["scope"].get("unresolved_objects")
        group["limitations"] = []
        if missing:
            group["limitations"].append({"reason": "Files are absent from the current source inventory", "files": missing})
        if group["scope"].get("unresolved_objects"):
            group["limitations"].append({"reason": "Source mapping is incomplete; keep original measurement objects"})
        limited = sorted(identity for identity in attached[group["group"]] if by_signal[identity]["suitability"] != "usable")
        if limited:
            group["limitations"].append({"reason": "Limited measurement evidence", "signals": limited})
        group["overlaps"] = sorted(overlaps[group["group"]], key=lambda overlap: overlap["group"])

    queue, covered, selected_count = [], {}, 0
    for position, group in enumerate(sorted(groups, key=lambda group: (-group["investigation_score"], group["group"])), 1):
        seeds = set(group["seed_signals"])
        covered_by = sorted({covered[identity] for identity in seeds if identity in covered})
        if seeds <= covered.keys():
            selected, reason = False, "Seed signals already included in selected groups; inspect before splitting"
        elif selected_count >= limit:
            selected, reason = False, "Candidate group limit reached; absence from the shortlist is not evidence of safety"
            covered_by = []
        else:
            selected, reason = True, "Next uncovered group by investigation score; equal scores use canonical scope order"
            selected_count += 1
            covered_by = []
            for identity in attached[group["group"]]:
                covered.setdefault(identity, group["group"])
        queue.append({"candidate_group": selection_reference("candidate-groups", "group", group["group"]),
                      "position": position, "investigation_score": group["investigation_score"], "selected": selected,
                      "reason": reason, "covered_by": covered_by, "evidence_families": group["evidence_families"]})

    for group in groups:
        group["seed_signals"] = [selection_reference("signals", "signal", identity) for identity in sorted(group["seed_signals"])]
        group["signals"] = [selection_reference("signals", "signal", identity) for identity in sorted(attached[group["group"]])]
    return {"signals": signals, "candidate-groups": groups, "investigation-queue": queue}
