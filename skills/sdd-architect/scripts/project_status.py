"""Build complete aggregate results; publish only as the final successful audit action."""

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from string import Template

from graph import module_for
from history import parse_history
from inputs import dependencies, relative_path, source_description
from quality_indicators import coverage_methods, indicators, qualify_kotlin


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
            "tools": {name: {key: metadata[key] for key in ("tool", "version", "parser_version", "command", "collected_at", "path") if key in metadata}
                      for name, metadata in artifacts.items()}, **result}


def render_status(value):
    def number(item):
        return "Неприменимо" if item is None else f"{item:.1f}"
    def percent(item):
        return "Неприменимо" if item is None else f"{100 * item:.1f}%"
    def label(name):
        return str(name).replace("|", "\\|").replace("\n", " ")
    summaries = [("Проект", value["project"]), *value["modules"].items()]
    scores = ["| Область Kotlin | Файлы Kotlin | Токены | D | L | U | Q |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, row in summaries:
        scores.append("| " + " | ".join([label(name), str(row["files"]), str(row["tokens"]), *(number(row[key]) for key in ("D", "L", "U", "Q"))]) + " |")
    sizes = ["| Область / категория / язык | Файлы | Строки | Код | Комментарии | Пустые |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, row in summaries:
        stats = row["statistics"]
        for suffix, counts in [("всего", stats["total"]), *sorted(stats["by_category"].items()), *sorted(stats["by_language"].items())]:
            sizes.append("| " + label(name + " / " + suffix) + " | " + " | ".join(str(counts[key]) for key in ("Files", "Lines", "Code", "Comment", "Blank")) + " |")
    diagnostics = []
    for name, row in summaries:
        structure, local, coverage, history = (row[key] for key in ("structure", "local_maintainability", "coverage", "history"))
        values = [
            ("PC", percent(structure["propagation_cost"])), ("Циклические файлы", str(structure["cyclic_files"])),
            ("Доля циклических файлов", percent(structure["cyclic_file_fraction"])), ("Крупнейшая SCC", str(structure["largest_scc_size"])),
            ("Рёбра", str(structure["edge_count"])), ("C_score", number(local["cognitive_score"])), ("S_score", number(local["size_score"])),
            ("Функции / токены функций / вне функций", f'{local["function_count"]} / {local["function_tokens"]} / {local["outside_function_tokens"]}'),
            ("Максимум / взвешенный p95 cognitive complexity", f'{number(local["maximum_cognitive_complexity"])} / {number(local["weighted_p95_cognitive_complexity"])}'),
            ("Сложные токены / доля", f'{local["complex_tokens"]} / {percent(local["complex_token_fraction"]["value"])}'),
            ("Повторяющиеся токены / доля", f'{row["duplication"]["tokens"]} / {percent(row["duplication"]["fraction"]["value"])}'),
            ("Покрытие ветвей / инструкций / строк", " / ".join(percent(coverage[key]["value"]) for key in ("branch", "instruction", "line"))),
            ("Методы CRAP_exec", str(coverage["method_count"])), ("Сумма CRAP_exec / превышение", f'{number(coverage["total_crap"])} / {number(coverage["total_excess"])}'),
            ("Превышение на 1000 токенов / E_CRAP / p95", " / ".join(number(coverage[key]) for key in ("excess_density", "E_CRAP", "p95_crap_exec"))),
            ("История: наблюдения / исключённые крупные коммиты", f'{history["observations"]} / {history["excluded_large_commits"]} ({history["status"]})'),
            ("Совместные изменения: файлы / токены / доля", f'{history["coupled_files"]} / {history["coupled_tokens"]} / {percent(history["coupled_token_fraction"]["value"])}'),
        ]
        if "boundary" in row:
            boundary = row["boundary"]
            values.extend([("Внешние входящие / исходящие рёбра", f'{boundary["incoming_edges"]} / {boundary["outgoing_edges"]}'),
                           ("Файлы в циклах полного графа проекта", str(boundary["project_cyclic_files"])),
                           ("Токены файлов с совместными изменениями через границу", str(boundary["cross_module_coupled_tokens"])),
                           ("Токены в межмодульных повторах", str(boundary["cross_module_duplicate_tokens"]))])
        diagnostics.extend(["### " + label(name), "", "| Показатель | Значение |", "| --- | ---: |",
                            *(f"| {key} | {item} |" for key, item in values), ""])
    template = Path(__file__).resolve().parents[1] / "assets" / "status.template.md"
    return Template(template.read_text(encoding="utf-8")).substitute(
        collected_at=value["collected_at"], audit=value["audit"], profile=value["profile"]["name"],
        scope=(f'{value["scope"]["kotlin_files"]} файлов Kotlin; {value["scope"]["other_production_files"]} прочих production-файлов. '
               f'Связи Kotlin с прочим production-кодом: входящих {value["scope"]["incoming_non_kotlin_edges"]}, '
               f'исходящих {value["scope"]["outgoing_non_kotlin_edges"]}.'),
        scores="\n".join(scores), statistics="\n".join(sizes), diagnostics="\n".join(diagnostics),
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
    for target in (destination / "status.json", destination / "status.md"):
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Status output leaves memory/tech-debt")
    (destination / "status.json").write_text(encoded, encoding="utf-8")
    (destination / "status.md").write_text(markdown, encoding="utf-8")
    return destination
