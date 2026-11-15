"""Normalize each input once, then prepare the full catalog before source diagnosis."""

import xml.etree.ElementTree as ET
from collections import defaultdict

from candidate_groups import prepare_candidate_groups
from graph import aggregate, graph_view, module_for, module_views, package_of
from history import group_activity, history_view, parse_history
from inputs import coverage, dependencies, detekt, ratio, sizes, type_counts
from measurements import CATALOG, key_text, ordered_rows, reference

def suitability(metadata):
    if metadata.get("status") != "complete":
        return "unusable"
    return "usable" if all(metadata.get(key) for key in ("tool", "version", "command")) else "limited"


def number(value, reason="Input is unavailable", **extra):
    return {"value": value, "status": "measured" if value is not None else "unknown",
            **({"reason": reason} if value is None else {}), **extra}


def prepare_measurements(config, sources, mappings, mapping_gaps, raw, artifacts, policy, source_error=None):
    """Pure calculation boundary: all filesystem and command I/O belongs to collect."""
    gaps = [{"artifact": "mapping", **gap} for gap in mapping_gaps]

    def parse(name, operation, empty):
        if name not in raw:
            return empty
        try:
            return operation(raw[name])
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, ET.ParseError) as error:
            artifacts[name].update(status="error", reason=str(error))
            return empty

    def parse_dependencies(text):
        if not config.get("package_prefixes"):
            raise ValueError("package_prefixes is required for dependency scope")
        return dependencies(text, artifacts["dependencies"]["format"], config["package_prefixes"], config.get("exclude_classes", []))

    edges = parse("dependencies", parse_dependencies, None)
    findings = parse("complexity", lambda text: detekt(text, artifacts["complexity"]["source_root"]), [])
    size_rows = parse("sizes", lambda text: sizes(text, artifacts["sizes"]["source_root"]), {})
    coverage_rows, coverage_gaps = parse("coverage", lambda text: coverage(text, artifacts["coverage"]["format"], artifacts["coverage"]["source_root"], sources), ({}, []))
    commits = parse("history", parse_history, None)
    history = history_view(commits, policy) if commits is not None else None
    if history is not None:
        artifacts["history"]["window"] = history["window"]
    gaps.extend({"artifact": "coverage", "reason": "Ambiguous or missing source mapping", **gap} for gap in coverage_gaps)
    for name, spec in artifacts.items():
        if spec.get("status") != "complete":
            gaps.append({"artifact": name, "reason": spec.get("reason", "Source is unavailable")})
    source_outcome = {"status": "complete"} if sources or config.get("source_roots") else {"status": "unavailable", "reason": "No source population supplied"}
    if source_error:
        source_outcome = {"status": "error", "reason": source_error}
        gaps.append({"artifact": "sources", "reason": source_error})
    mapping_outcome = ({"status": "complete"} if mappings or config.get("class_directories") or config.get("class_files")
                       else {"status": "unavailable", "reason": "No JVM-to-source mapping supplied"})
    if mapping_gaps and not mappings:
        mapping_outcome = {"status": "error", "reason": "JVM-to-source mapping could not be resolved"}
    inputs = {**artifacts, "sources": source_outcome, "mapping": mapping_outcome}
    rows, outcomes = {name: [] for name in CATALOG}, {}

    def emit(identifier, values, requires=None):
        required = requires if requires is not None else CATALOG[identifier]["inputs"]
        missing = [(name, inputs.get(name, {"status": "unavailable", "reason": "No source configured"}))
                   for name in required if inputs.get(name, {}).get("status") != "complete"]
        outcomes[identifier] = ({"status": "error" if any(spec["status"] == "error" for _, spec in missing) else "unavailable",
                                 "reason": "; ".join(f"{name}: {spec.get('reason', 'Unavailable')}" for name, spec in missing)}
                                if missing else {"status": "complete"})
        rows[identifier] = values

    for identifier in CATALOG:
        emit(identifier, [])
    emit("source-files/file", [{"file": path, "package": source["package"], "language": source.get("language", ".kt")}
                               for path, source in sources.items()])
    emit("class-files/class", [{"class": name, "file": path,
                                "source": "explicit" if name in config.get("class_files", {}) else "JVM SourceFile"}
                               for name, path in mappings.items()])
    for metric, field in (("type-count", "types"), ("abstract-type-count", "abstract")):
        emit(f"{metric}/file", [{"file": path, **number(source.get(field), "Declaration extraction is unavailable for this language")}
                                for path, source in sources.items()])
    if source_outcome["status"] == "complete":
        extra = sorted((set(size_rows) | set(coverage_rows) | {row["file"] for row in findings}) - set(sources))
        if extra:
            gaps.append({"reason": "Report paths outside production source population", "files": extra})
        size_rows = {path: row for path, row in size_rows.items() if path in sources}
        coverage_rows = {path: row for path, row in coverage_rows.items() if path in sources}
        findings = [row for row in findings if row["file"] in sources]

    modules = config.get("modules", {})
    owners, module_error = {}, None
    try:
        owners = {path: module_for(source["package"], modules) for path, source in sources.items()}
        for name in {node for edge in (edges or {}) for node in edge}:
            module_for(package_of(name), modules)
    except ValueError as error:
        module_error = str(error)
        gaps.append({"artifact": "modules", "reason": module_error})
    groups = {"package": defaultdict(list), "module": defaultdict(list)}
    for path, source in sources.items():
        groups["package"][source["package"]].append(path)
        if owners.get(path) is not None and not module_error:
            groups["module"][owners[path]].append(path)
    for module in modules:
        groups["module"][module]
    graphs = {}
    if edges is not None:
        package_edges = aggregate(edges, package_of)
        graph_edges = {"class": edges, "package": package_edges}
        if not module_error:
            graph_edges["module"] = aggregate(package_edges, lambda package: module_for(package, modules))
        for level, selected_edges in graph_edges.items():
            graph = graphs[level] = graph_view(selected_edges)
            emit(f"dependencies/{level}", [{"from": a, "to": b, "value": weight} for (a, b), weight in selected_edges.items()])
            for metric in ("node-count", "edge-count"):
                emit(f"{metric}/{level}", [{"graph": level, **number(graph[metric.replace('-', '_')])}])
            pc = graph["propagation_cost"]
            emit(f"propagation-cost/{level}", [{"graph": level, **pc, "status": "measured" if pc["denominator"] else "not_applicable"}])
            for metric in ("fan-in", "fan-out", "incoming-weight", "outgoing-weight", "reachable-in", "reachable-out", "visibility-in", "visibility-out"):
                values = []
                for node, value in graph["nodes"].items():
                    row = {"node": node, **number(value[metric.replace('-', '_')])}
                    if metric.startswith("visibility"):
                        row.update(numerator=value[metric.replace("visibility", "reachable").replace('-', '_')], denominator=graph["node_count"])
                    values.append(row)
                emit(f"{metric}/{level}", values)
            emit(f"cyclic-components/{level}", [{"members": group} for group in graph["cyclic_components"]])
            emit(f"cyclic-edges/{level}", [{"from": a, "to": b, "value": weight} for a, b, weight in graph["cyclic_edges"]])
            emit(f"dependency-layers/{level}", [{"members": layer["nodes"], "kind": layer["kind"], "position": index}
                                                for index, layer in enumerate(graph["layers"], 1)])
        counts = type_counts(sources)
        martin = module_views(package_edges, {}, counts, policy)["martin"]
        minimum_types = policy["measurements"]["martin"]["minimum_types"]
        for metric, field in (("ca", "Ca"), ("ce", "Ce"), ("instability", "I"), ("abstractness", "A"), ("distance", "D")):
            values = []
            for package, count in counts.items():
                value = martin.get(package)
                incomplete = any(source.get("types") is None for source in sources.values() if source["package"] == package)
                node = graphs["package"]["nodes"].get(package, {})
                type_unknown = incomplete and count["types"] < minimum_types and node.get("incoming_weight", 0) + node.get("outgoing_weight", 0) > 0
                values.append({"package": package, **number(value[field] if value else None,
                    "Type population is incomplete" if type_unknown else f"Requires at least {minimum_types} measured types and nonzero package weight"),
                    "types": count["types"], "abstract_types": count["abstract"],
                    "status": "measured_subset" if value and incomplete else "measured" if value else "unknown" if type_unknown else "not_applicable"})
            emit(f"{metric}/package", values)
        if not module_error:
            module_metrics = module_views(package_edges, modules, counts, policy)
            emit("cohesion/module", [{"module": name, **value, "status": "measured" if value["value"] is not None else "not_applicable"}
                                    for name, value in module_metrics["cohesion"].items()])
            emit("external-affinity/package", [{"package": name, **value} for name, value in module_metrics["external_affinity"].items()])

    rule_metrics = {"CyclomaticComplexMethod": "cyclomatic-complexity/function", "CognitiveComplexMethod": "cognitive-complexity/function",
                    "LongMethod": "method-length/function", "TooManyFunctions": "function-count/declaration", "LongParameterList": "parameter-list/declaration"}
    by_file = defaultdict(list)
    for finding in findings:
        if finding["rule"] == "LongParameterList" and finding["value"] is None and not finding["suppressed"]:
            gaps.append({"artifact": "complexity", "file": finding["file"], "record": finding["record"],
                         "reason": "Parameter count is unknown: obtain a complete supported declaration before applying the analyzer threshold"})
        by_file[finding["file"]].append(finding)
        rows[rule_metrics[finding["rule"]]].append({**finding, "status": "measured" if finding["value"] is not None else "unknown",
            **({"reason": "Cannot count parameters from a complete supported declaration" if finding["rule"] == "LongParameterList"
                          else "Tool message contains no measured value"} if finding["value"] is None else {})})
    paths = sorted(set(sources) | set(size_rows) | set(coverage_rows) | set(by_file) | (set(history["revisions"]) if history else set()))
    file_values = {}
    graph_nodes = graphs.get("class", {}).get("nodes", {})
    mapped_nodes = defaultdict(list)
    for name, node in graph_nodes.items():
        if name in mappings:
            mapped_nodes[mappings[name]].append(node)
    unmapped = sorted(set(graph_nodes) - set(mappings))
    if unmapped:
        gaps.append({"artifact": "mapping", "reason": "Dependency classes without a source mapping", "classes": unmapped})
    for path in paths:
        file_values[path] = {}
        for metric, field in (("code-lines", "Code"), ("total-lines", "Lines")):
            value = size_rows.get(path, {}).get(field)
            rows[f"{metric}/file"].append({"file": path, **number(value, "File was not measured by scc")})
        changes = history["revisions"].get(path, 0) if history is not None else None
        churn = history["churn"].get(path, {"added": 0, "deleted": 0, "binary_changes": 0}) if history is not None else None
        for metric, value in (("change-frequency", changes), ("added-lines", churn["added"] if churn else None),
                              ("deleted-lines", churn["deleted"] if churn else None),
                              ("churn", churn["added"] + churn["deleted"] if churn else None)):
            row = {"file": path, **number(value), "live_production": path in sources}
            if metric != "change-frequency":
                row["binary_changes"] = churn["binary_changes"] if churn else None
            rows[f"{metric}/file"].append(row)
            file_values[path][metric] = row
        mcc_findings = [row for row in by_file[path] if row["rule"] == "CyclomaticComplexMethod"]
        observed = [row["value"] for row in mcc_findings if row["value"] is not None and not row["suppressed"]]
        mcc = sum(observed) if observed else None
        complete = bool(artifacts.get("complexity", {}).get("complete_mcc")) and bool(observed) and all(
            row["value"] is not None and not row["suppressed"] for row in mcc_findings)
        rows["cyclomatic-complexity/file"].append({"file": path, **number(mcc, "No measured MCC finding"),
                                                  "population_complete": complete, "observed_functions": len(observed)})
        for kind in ("line", "branch"):
            counter = coverage_rows.get(path, {}).get(kind, {"covered": None, "total": None, "value": None, "status": "unknown", "reason": "File or counter was not measured"})
            rows[f"{kind}-coverage/file"].append({"file": path, **counter})
        line = coverage_rows.get(path, {}).get("line", {}).get("value")
        formula = policy["measurements"]["crap"]
        crap = (mcc ** formula["complexity_exponent"] * (1 - line) ** formula["uncovered_exponent"] + mcc
                if mcc is not None and line is not None else None)
        crap_row = {"file": path, **number(crap, "Requires measured MCC and line coverage"), "population_complete": complete}
        if crap is not None and not complete:
            crap_row["status"] = "measured_subset"
        rows["crap-file/file"].append(crap_row)
        file_values[path]["crap"] = crap_row
        mapped = mapped_nodes[path]
        for metric, visibility, activity in (("hotspot-in-frequency", "visibility_in", changes),
                                              ("hotspot-out-frequency", "visibility_out", changes),
                                              ("hotspot-in-churn", "visibility_in", file_values[path]["churn"]["value"])):
            maximum = max((node[visibility] for node in mapped), default=None)
            value = maximum * activity if maximum is not None and activity is not None else None
            rows[f"{metric}/file"].append({"file": path, **number(value, "Requires history and mapped dependency classes"),
                                          "visibility": maximum, "activity": activity, "mapping_complete": not unmapped and not mapping_gaps,
                                          **({"status": "measured_subset"} if value is not None and (unmapped or mapping_gaps) else {})})
        code = size_rows.get(path, {}).get("Code")
        density = policy["measurements"]["changes_per_code"]
        applicable = (path.endswith(".kt") and changes is not None and changes >= density["minimum_frequency"]
                      and code is not None and code >= density["minimum_code_lines"])
        row = {"file": path, **number(density["code_line_unit"] * changes / code if applicable else None,
               f"Requires Kotlin, frequency >= {density['minimum_frequency']} and code >= {density['minimum_code_lines']}")}
        if (not path.endswith(".kt") or (changes is not None and changes < density["minimum_frequency"])
                or (code is not None and code < density["minimum_code_lines"])):
            row["status"] = "not_applicable"
        rows["changes-per-code/file"].append(row)

    for level, members in groups.items():
        activity = group_activity(commits, {path: group for group, paths in members.items() for path in paths}, policy) if commits is not None else {}
        for group, paths in members.items():
            paths = sorted(paths)
            for metric in ("change-frequency", "added-lines", "deleted-lines", "churn"):
                values = [file_values[path][metric]["value"] for path in paths]
                row = {level: group, "files": paths, **number(sum(values) if history is not None else None)}
                if metric != "change-frequency":
                    row["binary_changes"] = sum(file_values[path][metric]["binary_changes"] for path in paths) if history is not None else None
                rows[f"{metric}/{level}"].append(row)
            for metric, field in (("activity", "commits"), ("recent-activity", "recent_commits")):
                rows[f"{metric}/{level}"].append({level: group, **number(activity.get(group, {}).get(field, 0) if commits is not None else None)})
            for kind in ("line", "branch"):
                measured = [path for path in paths if coverage_rows.get(path, {}).get(kind, {}).get("status") in {"measured", "not_applicable"}]
                omitted = sorted(set(paths) - set(measured))
                counters = [coverage_rows[path][kind] for path in measured]
                summary = ratio(sum(row["covered"] for row in counters), sum(row["total"] for row in counters)) if counters else {
                    "covered": None, "total": None, "value": None, "status": "unknown", "reason": "No measured counters"}
                if omitted:
                    summary["status"] = "measured_subset" if summary["value"] is not None else "unknown"
                rows[f"{kind}-coverage/{level}"].append({level: group, **summary, "included_files": measured, "omitted_files": omitted,
                                                         "not_applicable_files": [path for path in measured if coverage_rows[path][kind]["status"] == "not_applicable"]})
            included = [path for path in paths if file_values[path]["crap"]["value"] is not None]
            incomplete = [path for path in included if not file_values[path]["crap"]["population_complete"]]
            omitted = sorted(set(paths) - set(included))
            values = [file_values[path]["crap"]["value"] for path in included]
            for metric, value in (("crap-sum", sum(values) if values else None),
                                  ("crap-mean", sum(values) / len(values) if values else None),
                                  ("crap-above-threshold", sum(value > policy["signals"]["crap"]["minimum_value"] for value in values) if values else None)):
                rows[f"{metric}/{level}"].append({level: group, **number(value, "No measured CRAP_file values"),
                    "included_files": included, "omitted_files": omitted, "incomplete_files": incomplete,
                    **({"status": "measured_subset"} if value is not None and (omitted or incomplete) else {})})
    if commits is not None:
        rows["changes/commit"] = [{"commit": commit["revision"], "date": commit["date"], "changeset_size": len(commit["changes"]),
                                   "changes": [{"file": path, **change} for path, change in sorted(commit["changes"].items())]} for commit in commits]
        file_edges = {(mappings[a], mappings[b]) for a, b in (edges or {}) if a in mappings and b in mappings}
        for pair in history["coupling"]:
            left, right = pair["left"], pair["right"]
            row = {"left": left, "right": right, "left_frequency": pair["left_revisions"], "right_frequency": pair["right_revisions"],
                   "shared": pair["shared"], "average_frequency": pair["average_revisions"], "value": pair["degree"], "status": "measured"}
            row["live_production"] = left in sources and right in sources
            row["cross_package"] = row["live_production"] and sources[left]["package"] != sources[right]["package"]
            row["cross_module"] = owners[left] != owners[right] if owners.get(left) is not None and owners.get(right) is not None and not module_error else None
            rows["coupling/file-pair"].append(row)
            if left in sources and right in sources and sources[left]["package"] != sources[right]["package"] and left.endswith(".kt") and right.endswith(".kt"):
                direct = (left, right) in file_edges or (right, left) in file_edges
                if edges is not None and not direct:
                    rows["implicit-coupling/file-pair"].append({**row, "mapping_complete": not unmapped and not mapping_gaps and bool(mappings),
                        "status": "measured_subset" if unmapped or mapping_gaps or not mappings else "measured"})
    for identifier in CATALOG:
        if module_error and (identifier.endswith("/module") or identifier == "external-affinity/package"):
            rows[identifier] = []
            outcomes[identifier] = {"status": "error", "reason": module_error}
        rows[identifier] = ordered_rows(identifier, rows[identifier])
    selections = prepare_selections(rows, outcomes, artifacts, policy)
    selections.update(prepare_candidate_groups(config, rows, outcomes, selections["signals"], policy))
    return rows, outcomes, selections, gaps


def prepare_selections(rows, outcomes, artifacts, policy):
    rankings, signals = [], []
    filters = policy["signals"]

    def signal(family, condition, references):
        limited = any(row.get("status") == "measured_subset" or row.get("population_complete") is False for _, row in references)
        for identifier, _ in references:
            limited |= any(suitability(artifacts[name]) != "usable" for name in CATALOG[identifier]["inputs"] if name in artifacts)
        signals.append({"family": family, "condition": condition, "references": [reference(name, row) for name, row in references],
                        "suitability": "limited" if limited else "usable",
                        "evidence_weights": {criterion: min(weight, policy["evidence"]["limited_weight_cap"]) if limited else weight
                                             for criterion, weight in policy["evidence"]["weights"][family].items()}})

    for identifier in sorted(rows):
        if outcomes[identifier]["status"] != "complete":
            continue
        measured = [row for row in rows[identifier] if isinstance(row.get("value"), (int, float)) and not row.get("suppressed")]
        for position, row in enumerate(sorted(measured, key=lambda row: (-row["value"], key_text(reference(identifier, row)["key"]))), 1):
            rankings.append({"condition": "value descending; ties by record key", "position": position, **reference(identifier, row)})
        if identifier.startswith("cyclic-components/"):
            for row in rows[identifier]:
                if len(row["members"]) >= filters["cycle"]["minimum_members"]:
                    signal("cycle", f"members >= {filters['cycle']['minimum_members']}", [(identifier, row)])
        threshold = {
            "cyclomatic-complexity/function": (filters["complexity"]["cyclomatic_minimum"], "complexity"),
            "cognitive-complexity/function": (filters["complexity"]["cognitive_minimum"], "complexity"),
            "method-length/function": (filters["shape"]["method_length_minimum"], "shape"),
            "function-count/declaration": (filters["shape"]["function_count_minimum"], "shape"),
            "parameter-list/declaration": (filters["shape"]["parameter_list_minimum"], "shape"),
            "crap-file/file": (filters["crap"]["minimum_value"], "crap"),
            "distance/package": (filters["boundary"]["distance_minimum"], "boundary"),
        }.get(identifier)
        if threshold:
            value, family = threshold
            for row in measured:
                selected = row["value"] > value if family == "crap" else row["value"] >= value
                if selected:
                    signal(family, f"value {'>' if family == 'crap' else '>='} {value}", [(identifier, row)])
        if identifier.startswith("hotspot-"):
            hotspot = filters["hotspot"]
            for row in sorted(measured, key=lambda row: (-row["value"], row["file"]))[:hotspot["top_count"]]:
                if row["value"] > hotspot["minimum_score"]:
                    signal("hotspot", f"value > {hotspot['minimum_score']}; top {hotspot['top_count']}", [(identifier, row)])
            if identifier == "hotspot-in-frequency/file":
                for row in measured:
                    if row["activity"] >= hotspot["minimum_frequency"] and row["visibility"] >= hotspot["minimum_visibility"]:
                        signal("hotspot", f"frequency >= {hotspot['minimum_frequency']} and visibility_in >= {hotspot['minimum_visibility']}", [(identifier, row)])
        if identifier in {"coupling/file-pair", "implicit-coupling/file-pair"}:
            coupling = filters["coupling"]
            for row in measured:
                if (row["cross_package"] and row["average_frequency"] >= coupling["minimum_average_frequency"]
                        and row["shared"] >= coupling["minimum_shared_commits"] and row["value"] >= coupling["minimum_degree"]):
                    signal("coupling", f"cross_package and average_frequency >= {coupling['minimum_average_frequency']} "
                           f"and shared >= {coupling['minimum_shared_commits']} and degree >= {coupling['minimum_degree']}", [(identifier, row)])
    if all(outcomes[key]["status"] == "complete" for key in ("change-frequency/file", "line-coverage/file")):
        frequency = {row["file"]: row for row in rows["change-frequency/file"]}
        coverage_filter = filters["coverage"]
        for row in rows["line-coverage/file"]:
            activity = frequency.get(row["file"])
            if (activity and activity["value"] is not None and activity["value"] >= coverage_filter["minimum_frequency"]
                    and row["value"] is not None and row["value"] < coverage_filter["maximum_line_coverage"]):
                signal("coverage", f"frequency >= {coverage_filter['minimum_frequency']} and line coverage < {coverage_filter['maximum_line_coverage']}",
                       [("change-frequency/file", activity), ("line-coverage/file", row)])
    return {"rankings": rankings, "signals": sorted(signals, key=key_text)}
