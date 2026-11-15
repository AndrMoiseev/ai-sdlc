"""Executable measurement catalog and keyed JSONL references; see measurements.md."""

import json
from pathlib import Path


CATALOG = {}


def define(name, levels, key, unit, kind, inputs, meaning):
    for level in levels.split():
        identifier = f"{name}/{level}"
        CATALOG[identifier] = {"path": f"metrics/{identifier}.jsonl", "key": key.split(),
                               "unit": unit, "kind": kind, "inputs": inputs.split(),
                               "meaning": meaning}


define("source-files", "file", "file", "reference", "primary", "sources", "Current file, language and package")
define("class-files", "class", "class", "reference", "primary", "mapping", "JVM SourceFile or explicit mapping")
for name in ("type-count", "abstract-type-count"):
    define(name, "file", "file", "declarations", "primary", "sources", "Kotlin declaration heuristic; Java unmeasured")
define("dependencies", "class package module", "from to", "class pairs", "derived", "dependencies", "Unique consumer to supplier pairs; sum weights across boundaries")
CATALOG["dependencies/class"]["kind"] = "primary"
for name, unit, meaning in (
    ("node-count", "nodes", "Edge endpoints; isolated declarations excluded"),
    ("edge-count", "edges", "Unique directed pairs after aggregation"),
    ("propagation-cost", "fraction", "Reachable pairs including diagonal / N squared"),
):
    define(name, "class package module", "graph", unit, "derived", "dependencies", meaning)
for name, meaning in (
    ("fan-in", "Distinct immediate consumers"), ("fan-out", "Distinct immediate suppliers"),
    ("incoming-weight", "Sum of incoming class-pair weights"), ("outgoing-weight", "Sum of outgoing class-pair weights"),
    ("reachable-in", "Reachable consumers including self"), ("reachable-out", "Reachable suppliers including self"),
    ("visibility-in", "Reachable consumers including self / N"), ("visibility-out", "Reachable suppliers including self / N"),
):
    define(name, "class package module", "node", "fraction" if name.startswith("visibility") else "count", "derived", "dependencies", meaning)
define("cyclic-components", "class package module", "members", "reference", "derived", "dependencies", "SCC with more than one member")
define("cyclic-edges", "class package module", "from to", "class pairs", "derived", "dependencies", "Edges inside one cyclic SCC")
define("dependency-layers", "class package module", "members", "reference", "derived", "dependencies", "Peel no suppliers, no consumers, then largest SCC; position records sequence")
define("cohesion", "module", "module", "fraction", "derived", "dependencies", "Internal inter-package weight / (internal + boundary weight)")
define("external-affinity", "package", "package", "fraction", "derived", "dependencies", "External weight distribution across declared modules")
for name, meaning in (("ca", "Incoming package weight"), ("ce", "Outgoing package weight"),
                      ("instability", "Ce / (Ca + Ce)"), ("abstractness", "Abstract types / types"),
                      ("distance", "abs(A + I - 1)")):
    define(name, "package", "package", "class pairs" if name in ("ca", "ce") else "fraction", "derived", "sources dependencies", meaning + "; types meet policy minimum and Ca+Ce > 0")
define("changes", "commit", "commit", "event", "primary", "history", "Historical commit date, full changeset size and numstat paths")
for name, unit, meaning in (("change-frequency", "commits", "File commit count; group sum of file counts"),
                            ("added-lines", "lines", "Sum of textual additions"), ("deleted-lines", "lines", "Sum of textual deletions"),
                            ("churn", "lines", "Added plus deleted lines; binary changes retain separate count")):
    define(name, "file package module", "file", unit, "derived", "history", meaning)
    for level in ("package", "module"):
        CATALOG[f"{name}/{level}"]["key"] = [level]
        CATALOG[f"{name}/{level}"]["inputs"].append("sources")
for name, meaning in (("activity", "Distinct commits touching group in history window"),
                      ("recent-activity", "Distinct group commits since latest log date minus policy recent_days, inclusive")):
    for level in ("package", "module"):
        define(name, level, level, "commits", "derived", "sources history", meaning)
define("coupling", "file-pair", "left right", "percent", "derived", "history", "floor(200*shared/(left_frequency+right_frequency)); policy changeset-size filter before all support counts")
define("implicit-coupling", "file-pair", "left right", "percent", "derived", "history dependencies sources", "Coupled live Kotlin files in different packages without an observed direct static edge; absent or partial mapping limits the claim")
for name, field in (("code-lines", "Code"), ("total-lines", "Lines")):
    define(name, "file", "file", "lines", "primary", "sizes", "scc " + field)
for name, level, unit, rule in (
    ("cyclomatic-complexity", "function", "complexity", "CyclomaticComplexMethod"),
    ("cognitive-complexity", "function", "complexity", "CognitiveComplexMethod"),
    ("method-length", "function", "lines", "LongMethod"),
    ("function-count", "declaration", "functions", "TooManyFunctions"),
    ("parameter-list", "declaration", "parameters", "LongParameterList"),
):
    define(name, level, "file region declaration", unit, "primary", "complexity", f"detekt {rule}; retain location, message, suppression and unknown values")
define("cyclomatic-complexity", "file", "file", "complexity", "derived", "complexity", "Sum of observed unsuppressed MCC; absence is unknown, completeness explicit")
for name in ("line-coverage", "branch-coverage"):
    for level in ("file", "package", "module"):
        define(name, level, level, "fraction", "primary" if level == "file" else "derived", "coverage", "covered / total; group sums of counters with explicit omissions")
        if level != "file":
            CATALOG[f"{name}/{level}"]["inputs"].append("sources")
define("crap-file", "file", "file", "adapted CRAP", "derived", "complexity coverage", "observed_MCC**complexity_exponent * (1-line_coverage)**uncovered_exponent + observed_MCC; exponents from policy; incomplete population retained")
for name, meaning in (("crap-sum", "Sum"), ("crap-mean", "Mean"), ("crap-above-threshold", "Count above policy CRAP minimum")):
    for level in ("package", "module"):
        define(name, level, level, "files" if name == "crap-above-threshold" else "adapted CRAP", "derived", "complexity coverage sources", meaning + " of defined CRAP_file values; included, omitted and incomplete files explicit")
for name, meaning in (("hotspot-in-frequency", "max class visibility_in * file change_frequency"),
                      ("hotspot-out-frequency", "max class visibility_out * file change_frequency"),
                      ("hotspot-in-churn", "max class visibility_in * file churn")):
    define(name, "file", "file", "weighted lines" if name.endswith("churn") else "weighted commits", "derived", "dependencies history mapping", meaning)
define("changes-per-code", "file", "file", "commits per configured code-line unit", "derived", "history sizes", "code_line_unit * change_frequency / Code; Kotlin, policy minimum frequency and Code")


def record_key(identifier, row):
    return {field: row[field] for field in CATALOG[identifier]["key"]}


def key_text(key):
    return json.dumps(key, sort_keys=True, ensure_ascii=False, allow_nan=False)


def ordered_rows(identifier, rows):
    keyed = [(key_text(record_key(identifier, row)), row) for row in rows]
    if len({key for key, _ in keyed}) != len(keyed):
        raise ValueError(f"Duplicate measurement key: {identifier}")
    return [row for _, row in sorted(keyed, key=lambda pair: pair[0])]


def reference(identifier, row):
    return {"path": CATALOG[identifier]["path"], "key": record_key(identifier, row)}


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def resolve_reference(reference, collection, directory):
    """Read only the cited measurement, addressed by its complete object key."""
    path, key = reference.get("path"), reference.get("key")
    identifier = next((name for name, spec in CATALOG.items() if spec["path"] == path), None)
    if identifier is None or not isinstance(key, dict) or set(key) != set(CATALOG[identifier]["key"]):
        raise ValueError("Metric evidence needs a catalog path and its complete record key")
    output = collection["outputs"].get(identifier, {})
    if output.get("status") != "complete":
        raise ValueError(f"Metric evidence is unavailable: {identifier}")
    directory = Path(directory).resolve()
    target = (directory / path).resolve()
    if not target.is_relative_to(directory):
        raise ValueError("Metric evidence leaves report directory")
    matches = []
    with target.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if record_key(identifier, row) == key:
                    matches.append(row)
    if len(matches) != 1:
        raise ValueError(f"Metric evidence key must resolve to one record: {identifier} {key}")
    return matches[0]
