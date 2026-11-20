"""Build complete aggregate results; publish only as the final successful audit action."""

import json
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from string import Template

from graph import module_for
from history import parse_history
from inputs import dependencies, relative_path, source_description
from quality_indicators import coverage_methods, indicators, qualify_kotlin


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def statistics(text, config, sources, root, source_root=None):
    counters = ("Files", "Lines", "Code", "Comment", "Blank")
    def empty():
        return {key: 0 for key in counters}
    def group():
        return {"total": empty(), "by_language": defaultdict(empty), "by_category": defaultdict(empty)}
    project, modules, seen = group(), {name: group() for name in config["modules"]}, set()
    rows = []
    exclusions = [*config.get("exclude_paths", []), *config.get("statistics_exclude_paths", []), "memory/tech-debt/**"]
    for language in json.loads(text):
        for row in language.get("Files", []):
            path = relative_path(row["Location"], source_root or root)
            if path in seen:
                raise ValueError(f"Duplicate scc file: {path}")
            seen.add(path)
            if any(fnmatchcase(path, pattern) for pattern in exclusions):
                continue
            values = {"Files": 1, **{key: row[key] for key in counters if key != "Files"}}
            if any(type(value) is not int or value < 0 for value in values.values()):
                raise ValueError(f"Invalid scc counters: {path}")
            category = "production" if path in sources else "tests" if any(path.startswith(p.rstrip("/") + "/") for p in config.get("test_roots", [])) else "other"
            source = sources.get(path)
            if source is None and category == "tests" and Path(path).suffix in {".kt", ".java"}:
                source = source_description((root / path).read_text(encoding="utf-8-sig"), Path(path).suffix)
            owner = module_for(source["package"], config["modules"]) if source else None
            for target in [project, *([modules[owner]] if owner else [])]:
                for destination in (target["total"], target["by_language"][language["Name"]], target["by_category"][category]):
                    for key, value in values.items():
                        destination[key] += value
            rows.append(path)
    missing = set(sources) - set(rows)
    if missing:
        raise ValueError("scc omits production files: " + ", ".join(sorted(missing)[:10]))
    return {"project": project, "modules": modules, "exclusions": exclusions}


def prepare_status(config, sources, mappings, raw, artifacts, policy, *, repository):
    files = qualify_kotlin(json.loads(raw["kotlin"]), sources)
    class_edges = dependencies(raw["dependencies"], artifacts["dependencies"]["format"],
                               config["package_prefixes"], config.get("exclude_classes", []))
    missing = {name for edge in class_edges for name in edge if name not in mappings}
    if missing:
        raise ValueError("jdeps classes have no source mapping: " + ", ".join(sorted(missing)[:10]))
    edges = {(mappings[a], mappings[b]) for a, b in class_edges if mappings[a] != mappings[b]}
    metadata = artifacts["coverage"]
    if metadata.get("format") != "jacoco" or metadata.get("complete") is not True or metadata.get("test_result") != "passed":
        raise ValueError("Coverage requires complete JaCoCo XML and a passed selected test run; configure coverage first")
    kotlin_sources = {path: sources[path] for path in files}
    methods, lines = coverage_methods(raw["coverage"], kotlin_sources, mappings)
    history = json.loads(raw["history"])
    if history.get("format") != "git-history" or not history.get("first_parent") or not history.get("renames"):
        raise ValueError("Full audit requires first-parent history with rename tracking")
    as_of = datetime.now(timezone.utc).date()
    cutoff = as_of - timedelta(days=policy["measurements"]["quality_indicators"]["history_days"])
    if date.fromisoformat(history["since"]) > cutoff or date.fromisoformat(history["until"]) < as_of:
        raise ValueError("History does not cover the configured observation window; collect the required history")
    result = indicators(files, edges, config["modules"], methods, lines, parse_history(raw["history"]),
                        policy["measurements"]["quality_indicators"], as_of)
    root = Path(repository)
    size = statistics(raw["sizes"], config, sources, root, root / artifacts["sizes"].get("source_root", "."))
    result["project"]["statistics"] = size["project"]
    for name, value in result["modules"].items():
        value["statistics"] = size["modules"][name]
    return {"schema_version": 1, "collected_at": datetime.now(timezone.utc).isoformat(),
            "profile": {"name": "kotlin-jvm-jdeps-archdrh-re-1", "parameters": policy["measurements"]["quality_indicators"],
                        "dependencies": "jdeps class dependencies projected onto source files",
                        "module_scope": "induced file graph; local clones; separate boundary exposure",
                        "kotlin_metric_tool": json.loads(raw["kotlin"])["tool_version"]},
            "scope": {"source_roots": config["source_roots"], "test_roots": config.get("test_roots", []),
                      "modules": config["modules"], "statistics_exclusions": size["exclusions"],
                      "exclude_paths": config.get("exclude_paths", []), "exclude_classes": config.get("exclude_classes", []),
                      "class_directories": config.get("class_directories", []), "build": config.get("scope", {}),
                      "incoming_non_kotlin_edges": sum(a not in files and b in files for a, b in edges),
                      "outgoing_non_kotlin_edges": sum(a in files and b not in files for a, b in edges),
                      "kotlin_files": len(files), "other_production_files": len(sources) - len(files)},
            "limitations": ["jdeps reflects compiled dependencies; inline, reflection and DI can hide source/runtime relationships",
                            "D uses the documented ArchDRH-Re implementation; real-project calibration is pending",
                            "Module D/PC describe internal structure; cross-module edges are reported separately",
                            "Module Q values are recomputed and must not be averaged into project Q",
                            "Exact token clones preserve identifiers and literals; renamed clones may be missed"],
            "tools": {name: {key: metadata[key] for key in ("tool", "version", "parser_version", "plugin_version", "command", "collected_at", "path") if key in metadata}
                      for name, metadata in artifacts.items()}, **result}


def render_status(value):
    def number(item):
        return "Неприменимо" if item is None else f"{item:.1f}"
    def percent(item):
        return "Неприменимо" if item is None else f"{100 * item:.1f}%"
    def label(name):
        return str(name).replace("|", "\\|").replace("\n", " ")
    summaries = [("Проект", value["project"]), *value["modules"].items()]
    scores, sizes, diagnostics, boundaries = [], [], [], []
    diagnostic_template = Template((ASSETS / "status-diagnostics.template.md").read_text(encoding="utf-8"))
    for name, row in summaries:
        scores.append("| " + " | ".join([label(name), str(row["files"]), str(row["tokens"]),
                                         *(number(row[key]) for key in ("D", "L", "U", "Q"))]) + " |")
        stats = row["statistics"]
        for suffix, counts in [("всего", stats["total"]), *sorted(stats["by_category"].items()), *sorted(stats["by_language"].items())]:
            sizes.append("| " + label(name + " / " + suffix) + " | " + " | ".join(str(counts[key]) for key in ("Files", "Lines", "Code", "Comment", "Blank")) + " |")
        structure, local, coverage, history = (row[key] for key in ("structure", "local_maintainability", "coverage", "history"))
        line = coverage["line"]
        omitted = line["omitted_files"]
        line_value = "Нет данных" if line["status"] == "unknown" else percent(line["value"])
        if line["status"] == "measured_subset":
            line_value += " (по части файлов)"
        diagnostics.append(diagnostic_template.substitute(
            name=label(name), pc=percent(structure["propagation_cost"]),
            cyclic_files=structure["cyclic_files"], cyclic_file_fraction=percent(structure["cyclic_file_fraction"]),
            largest_scc_size=structure["largest_scc_size"], edge_count=structure["edge_count"],
            function_count=local["function_count"], function_tokens=local["function_tokens"],
            outside_function_tokens=local["outside_function_tokens"], complex_tokens=local["complex_tokens"],
            complex_token_fraction=percent(local["complex_token_fraction"]["value"]),
            duplicate_tokens=row["duplication"]["tokens"], duplicate_token_fraction=percent(row["duplication"]["fraction"]["value"]),
            method_count=coverage["method_count"], observations=history["observations"], history_status=history["status"],
            excluded_large_commits=history["excluded_large_commits"], coupled_files=history["coupled_files"],
            coupled_tokens=history["coupled_tokens"], coupled_token_fraction=percent(history["coupled_token_fraction"]["value"]),
            **{key: number(local[key]) for key in ("cognitive_score", "size_score", "maximum_cognitive_complexity", "weighted_p95_cognitive_complexity")},
            branch=percent(coverage["branch"]["value"]), instruction=percent(coverage["instruction"]["value"]),
            line=line_value, omitted_files=("\nФайлы без построчных данных JaCoCo\n\n" +
                                          "\n".join("- " + label(path) for path in omitted)) if omitted else "",
            **{key: number(coverage[key]) for key in ("total_crap", "total_excess", "excess_density", "E_CRAP", "p95_crap_exec")},
        ).rstrip())
        if "boundary" in row:
            boundary = row["boundary"]
            counts = (boundary[key] for key in ("incoming_edges", "outgoing_edges", "project_cyclic_files",
                                                "cross_module_coupled_tokens", "cross_module_duplicate_tokens"))
            boundaries.append("| " + " | ".join([label(name), *map(str, counts)]) + " |")
    return Template((ASSETS / "status.template.md").read_text(encoding="utf-8")).substitute(
        collected_at=value["collected_at"], audit=value["audit"], profile=value["profile"]["name"], **value["scope"],
        scores="\n".join(scores), statistics="\n".join(sizes), diagnostics="\n\n".join(diagnostics), boundaries="\n".join(boundaries),
        limitations="\n".join("- " + text for text in value["limitations"]))


def publish_status(collection_path, repository):
    description = json.loads(collection_path.read_text(encoding="utf-8-sig"))
    root = Path(repository).resolve()
    audit = collection_path.resolve().parent
    from collection import report_output
    report_output(audit, root, directory=True)
    if description.get("route") != "full" or description.get("status") != "complete":
        raise ValueError("Publish status only after a complete full audit")
    if any(metadata.get("status") != "complete" for metadata in description["artifacts"].values()):
        raise ValueError("A required measurement source failed; resolve it before publishing status")
    for required in (audit / "report.md", root / "memory/tech-debt/plan/plan.md"):
        if not required.is_file():
            raise ValueError(f"Finish the report and tech debt plan before status publication: {required}")
    artifact = description.get("quality_indicators", {})
    if artifact.get("status") != "complete":
        raise ValueError("Aggregate calculations are incomplete")
    path = (audit / artifact["path"]).resolve()
    if not path.is_relative_to(audit):
        raise ValueError("Aggregate input must be inside the selected audit")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    value["audit"] = audit.relative_to(root / "memory/tech-debt").as_posix()
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    # Prepare rendering before the final plain writes; no backup or rollback protocol.
    markdown = render_status(value)
    destination = root / "memory/tech-debt"
    guide = destination / "status-indicators.md"
    for target in (destination / "status.json", destination / "status.md", guide):
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Status output leaves memory/tech-debt")
    shutil.copyfile(ASSETS / guide.name, guide)
    (destination / "status.json").write_text(encoded, encoding="utf-8")
    (destination / "status.md").write_text(markdown, encoding="utf-8")
    return destination
