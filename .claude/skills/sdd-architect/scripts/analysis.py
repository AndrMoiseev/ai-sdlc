"""Deterministic measurement views and investigation signals, never diagnoses."""

import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from collection import digest
from graph import aggregate, graph_view, module_for, module_views, package_of
from history import group_activity, history_view, parse_history
from inputs import coverage, dependencies, detekt, ratio, sizes, type_counts

WEIGHTS = {"cycle": [2, 1, 1], "centrality": [1, 1, 0], "layers": [1, 0, 0],
           "module": [1, 0, 0], "coupling": [2, 1, 1], "hotspot": [2, 1, 1],
           "history": [1, 1, 1], "complexity": [1, 2, 1], "shape": [1, 1, 1],
           "size": [1, 0, 1], "coverage": [0, 2, 0], "crap": [0, 2, 0], "context": [0, 0, 0]}


def suitability(snapshot, metadata):
    if metadata.get("source_state") and metadata["source_state"] != snapshot.get("source_state"):
        return "unusable", "source state differs"
    if metadata.get("revision") and snapshot.get("revision") and metadata["revision"] != snapshot["revision"]:
        return "unusable", "revision differs"
    if not metadata.get("source_state") or not metadata.get("revision"):
        return "limited", "source state or revision unverified"
    if not all(metadata.get(key) for key in ("tool", "version", "command")):
        return "limited", "tool version or collection command missing"
    return "usable", "revision, source state and collection provenance match"


def analyze(snapshot, directory):
    sources = snapshot.get("source_files", {})
    modules = snapshot.get("modules", {})
    mapping_status = snapshot.get("mapping_status", "limited")
    mappings = snapshot.get("class_files", {}) if mapping_status != "unusable" else {}
    artifacts = snapshot.get("artifacts", {})
    statuses, raw, gaps = {}, {}, list(snapshot.get("gaps", []))
    for name, metadata in artifacts.items():
        status, reason = suitability(snapshot, metadata)
        path = (directory / metadata["path"]).resolve()
        if directory.resolve() not in path.parents:
            raise ValueError(f"Artifact leaves snapshot directory: {name}")
        data = path.read_bytes()
        if digest(data) != metadata["sha256"]:
            status, reason = "unusable", "artifact checksum differs"
        statuses[name] = {"status": status, "reason": reason, "sha256": metadata["sha256"]}
        if status != "unusable":
            raw[name] = data.decode("utf-8-sig")
        else:
            gaps.append({"artifact": name, "reason": reason})
    def parse(name, operation, empty):
        if name not in raw:
            return empty
        try:
            return operation(raw[name])
        except (ValueError, KeyError, TypeError, ET.ParseError) as error:
            statuses[name] = {"status": "unusable", "reason": str(error)}
            gaps.append({"artifact": name, "reason": str(error)})
            return empty
    edges = parse("dependencies", lambda text: dependencies(text, artifacts["dependencies"]["format"],
                  snapshot["package_prefixes"], snapshot.get("exclude_classes", [])), None)
    findings = parse("complexity", lambda text: detekt(text, artifacts["complexity"]["source_root"]), [])
    size_rows = parse("sizes", lambda text: sizes(text, artifacts["sizes"]["source_root"]), {})
    coverage_rows, coverage_gaps = parse("coverage", lambda text: coverage(text, artifacts["coverage"]["format"],
                artifacts["coverage"]["source_root"], sources), ({}, []))
    commits = parse("history", parse_history, None)
    history = history_view(commits) if commits is not None else None
    coverage_gaps = [{"artifact": "coverage", "reason": "ambiguous or missing source mapping", **row}
                     for row in coverage_gaps]
    gaps.extend(coverage_gaps)
    if sources:
        out_of_scope = sorted((set(size_rows) | set(coverage_rows) | {f["file"] for f in findings}) - set(sources))
        if out_of_scope:
            gaps.append({"reason": "report paths outside production source inventory", "files": out_of_scope})
        size_rows = {key: row for key, row in size_rows.items() if key in sources}
        coverage_rows = {key: row for key, row in coverage_rows.items() if key in sources}
        findings = [row for row in findings if row["file"] in sources]
    package_edges = aggregate(edges, package_of) if edges is not None else None
    graphs = {}
    if edges is not None:
        if not snapshot.get("package_prefixes"):
            raise ValueError("package_prefixes is required to define the dependency graph scope")
        graphs["class"] = graph_view(edges)
        graphs["package"] = graph_view(package_edges)
        graphs["module"] = graph_view(aggregate(package_edges, lambda package: module_for(package, modules)))
    module_metrics = module_views(package_edges, modules, type_counts(sources)) if package_edges is not None else None
    observed_mcc, by_file, incomplete_mcc = defaultdict(int), defaultdict(list), set()
    for finding in findings:
        by_file[finding["file"]].append(finding)
        if finding["rule"] == "CyclomaticComplexMethod" and finding["value"] is not None and not finding["suppressed"]:
            observed_mcc[finding["file"]] += finding["value"]
        elif finding["rule"] == "CyclomaticComplexMethod":
            incomplete_mcc.add(finding["file"])
    mapped_nodes = defaultdict(list)
    class_nodes = graphs.get("class", {}).get("nodes", {})
    for name, node in class_nodes.items():
        if name in mappings:
            mapped_nodes[mappings[name]].append(node)
    mapping = {"mapped": sum(name in mappings for name in class_nodes), "total": len(class_nodes),
               "unmapped": sorted(set(class_nodes) - set(mappings)), "details": snapshot.get("mapping_gaps", []),
               "suitability": mapping_status, "source_states": snapshot.get("mapping_source_states", [])}
    files, signals = {}, []
    def signal(family, subject, values, artifact_names, record, limited=False):
        available = [statuses.get(name, {"status": "unusable"})["status"] for name in artifact_names]
        status = "unusable" if "unusable" in available else "limited" if "limited" in available or limited else "usable"
        weights = [0, 0, 0] if status == "unusable" else [min(weight, 1) for weight in WEIGHTS[family]] if status == "limited" else WEIGHTS[family]
        signals.append({"family": family, "subject": subject, "values": values, "source": record,
                        "provenance_groups": artifact_names, "suitability": status, "weights_MRS": weights})
    if graphs:
        # Package cycles are useful even when module ownership has not been established.
        for group in graphs["package"]["cyclic_components"]:
            signal("cycle", group, {"size": len(group)}, ["dependencies"], "graphs/package/cyclic_components")
    paths = sorted(set(sources) | set(size_rows) | set(coverage_rows) | set(by_file))
    for path in paths:
        revisions = history["revisions"].get(path, 0) if history is not None else None
        churn = history["churn"].get(path, {"added": 0, "deleted": 0, "binary_changes": 0}) if history is not None else None
        size, cov, mcc = size_rows.get(path), coverage_rows.get(path), observed_mcc.get(path)
        line = cov["line"]["value"] if cov else None
        file_crap = mcc**2 * (1 - line)**3 + mcc if mcc is not None and line is not None else None
        nodes = mapped_nodes.get(path, [])
        visibility_in = max((node["visibility_in"] for node in nodes), default=None)
        visibility_out = max((node["visibility_out"] for node in nodes), default=None)
        row = {"package": sources.get(path, {}).get("package"), "size": size, "revisions": revisions,
               "churn": churn, "coverage": cov, "mcc_sum_observed": mcc, "CRAP_file": file_crap,
               "mcc_population_complete": bool(artifacts.get("complexity", {}).get("complete_mcc")) and path not in incomplete_mcc,
               "findings": by_file.get(path, []), "visibility_in": visibility_in, "visibility_out": visibility_out,
               "H_in_revisions": visibility_in * revisions if visibility_in is not None and revisions is not None else None,
               "H_out_revisions": visibility_out * revisions if visibility_out is not None and revisions is not None else None,
               "H_in_churn": visibility_in * (churn["added"] + churn["deleted"]) if visibility_in is not None and churn is not None else None,
               "revisions_per_100_code": 100 * revisions / size["Code"] if path.endswith(".kt") and revisions is not None
                   and revisions >= 5 and size and size["Code"] >= 20 else None}
        files[path] = row
        for finding in row["findings"]:
            thresholds = {"CyclomaticComplexMethod": 10, "CognitiveComplexMethod": 15, "LongMethod": 20, "TooManyFunctions": 11}
            value = finding["value"]
            if not finding["suppressed"] and value is not None and value >= thresholds.get(finding["rule"], float("inf")):
                family = "complexity" if finding["rule"] in {"CyclomaticComplexMethod", "CognitiveComplexMethod"} else "shape"
                signal(family, path, {"rule": finding["rule"], "value": value, "threshold": thresholds[finding["rule"]]},
                       ["complexity"], finding["record"])
        if line is not None and revisions is not None and revisions >= 13 and line < .5:
            signal("coverage", path, {"revisions": revisions, "line": cov["line"]}, ["history", "coverage"], f"files/{path}/coverage")
        if file_crap is not None and file_crap > 30:
            signal("crap", path, {"CRAP_file": file_crap, "mcc_sum_observed": mcc, "coverage": cov["line"]},
                   ["complexity", "coverage"], f"files/{path}/CRAP_file", limited=not row["mcc_population_complete"])
    rankings = {}
    for key in ("H_in_revisions", "H_in_churn", "H_out_revisions", "revisions_per_100_code"):
        rankings[key] = sorted([{"file": path, "value": row[key]} for path, row in files.items() if row[key] is not None],
                               key=lambda row: (-row["value"], row["file"]))
    hotspot_paths = {row["file"] for key in ("H_in_revisions", "H_in_churn", "H_out_revisions") for row in rankings[key][:5] if row["value"] > 0}
    hotspot_paths.update(path for path, row in files.items() if row["revisions"] is not None and row["revisions"] >= 10
                        and row["visibility_in"] is not None and row["visibility_in"] >= .05)
    for path in sorted(hotspot_paths):
        signal("hotspot", path, {key: files[path][key] for key in ("revisions", "visibility_in", "visibility_out", "H_in_revisions", "H_in_churn", "H_out_revisions")},
               ["dependencies", "history"], f"files/{path}", limited=bool(mapping["unmapped"]) or mapping_status != "usable")
    file_edges = {(mappings[a], mappings[b]) for a, b in (edges or {}) if a in mappings and b in mappings}
    if history is not None:
        for pair in history["coupling"]:
            left, right = pair["left"], pair["right"]
            pair["live_production"] = left in sources and right in sources
            pair["cross_package"] = pair["live_production"] and sources[left]["package"] != sources[right]["package"]
            owner_left = module_for(sources[left]["package"], modules) if left in sources else None
            owner_right = module_for(sources[right]["package"], modules) if right in sources else None
            pair["cross_module"] = None if owner_left is None or owner_right is None else owner_left != owner_right
            direct = (left, right) in file_edges or (right, left) in file_edges
            pair["no_direct_static_edge_observed"] = None if edges is None else not direct
            pair["static_absence_suitability"] = ("unusable" if edges is None or mapping_status == "unusable" else "limited"
                if mapping["unmapped"] or mapping_status != "usable" or statuses["dependencies"]["status"] != "usable" else "usable")
            pair["implicit_coupling_candidate"] = bool(pair["cross_package"] and left.endswith(".kt") and right.endswith(".kt")
                                                        and edges is not None and not direct)
            if pair["cross_package"]:
                support = {key: pair[key] for key in ("left_revisions", "right_revisions", "shared", "average_revisions", "degree", "cross_module")}
                signal("coupling", [left, right], support, ["history"], f"history/coupling/{left}|{right}")
        owners = {path: module_for(source["package"], modules) for path, source in sources.items()}
        history["module_activity"] = group_activity(commits, owners)
        history["absent_paths"] = sorted(set(history["revisions"]) - set(sources)) if sources else None
    groups = {"package": defaultdict(list), "module": defaultdict(list)}
    for path, row in files.items():
        if row["package"] is not None:
            groups["package"][row["package"]].append(path)
            owner = module_for(row["package"], modules)
            if owner is not None:
                groups["module"][owner].append(path)
    aggregates = {}
    for level, members in groups.items():
        aggregates[level] = {}
        for group, paths in sorted(members.items()):
            included = [path for path in paths if files[path]["CRAP_file"] is not None]
            coverage_totals = {}
            for kind in ("line", "branch"):
                measured_paths = [path for path in paths if files[path]["coverage"]
                                  and files[path]["coverage"][kind]["status"] != "unknown"]
                counters = [files[path]["coverage"][kind] for path in measured_paths]
                omitted_paths = sorted(set(paths) - set(measured_paths))
                summary = ratio(sum(c["covered"] for c in counters), sum(c["total"] for c in counters)) if counters else {
                    "covered": None, "total": None, "value": None, "status": "unknown"}
                if omitted_paths and summary["status"] == "measured":
                    summary["status"] = "measured_subset"
                elif omitted_paths and summary["status"] == "not_applicable":
                    summary["status"] = "unknown"
                coverage_totals[kind] = {**summary, "included_files": measured_paths, "omitted_files": omitted_paths,
                                        "not_applicable_files": [path for path in measured_paths if files[path]["coverage"][kind]["status"] == "not_applicable"]}
            values = [files[path]["CRAP_file"] for path in included]
            aggregates[level][group] = {"files": paths, "crap_files": included, "crap_sum": sum(values) if values else None,
                                        "crap_mean": sum(values) / len(values) if values else None,
                                        "crap_above_30": sum(value > 30 for value in values), "coverage": coverage_totals}
    return {"schema_version": 1, "revision": snapshot.get("revision"), "source_state": snapshot.get("source_state"),
            "source_available": bool(sources), "scope": snapshot.get("scope", {}), "modules": modules,
            "artifact_status": statuses, "gaps": gaps, "mapping": mapping,
            "graphs": graphs, "module_metrics": module_metrics, "history": history,
            "files": files, "aggregates": aggregates, "rankings": rankings, "signals": signals,
            "limits": ["Signals select investigations; they do not establish a diagnosis or implementation priority.",
                       "Graph nodes are edge endpoints; isolated declarations are absent. Nested JVM classes are preserved.",
                       "Unknown packages are not an architectural module. Gradle projects describe collection scope.",
                       "No static edge observed does not exclude transitive, DI, reflection or runtime coupling."]}
