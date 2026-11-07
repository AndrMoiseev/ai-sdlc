"""Strict adapters for the measured rows; absent values stay absent."""

import csv
import io
import json
import re
import struct
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

RULES = {
    "CyclomaticComplexMethod": r"Cyclomatic Complexity \(complexity: (\d+)\)",
    "CognitiveComplexMethod": r"Cognitive Complexity \(complexity: (\d+)\)",
    "LongMethod": r"too long \((\d+)\)",
    "TooManyFunctions": r"with '(\d+)' functions",
    "LongParameterList": None,
}


def relative_path(value, root):
    value = unquote(value)
    if value.startswith("file:"):
        parsed = urlparse(value)
        value = ("//" + parsed.netloc if parsed.netloc else "") + parsed.path
        if re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]
    value, root = value.replace("\\", "/"), str(root).replace("\\", "/").rstrip("/")
    # A supplied original root allows imported reports from a different computer.
    if value == root:
        raise ValueError("Expected a source file, got the repository root")
    if value.startswith(root + "/"):
        value = value[len(root) + 1:]
    path = PurePosixPath(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", value) or ".." in path.parts:
        raise ValueError(f"Unmapped source path {value!r}; set the artifact's source_root")
    return str(path)


def dependencies(text, format_name, prefixes, excludes=()):
    from fnmatch import fnmatchcase
    pairs = []
    if format_name == "class-csv":
        reader = csv.DictReader(io.StringIO(text))
        if not {"from", "to"}.issubset(reader.fieldnames or []):
            raise ValueError("Dependencies CSV requires from,to headers")
        pairs = [(row["from"], row["to"]) for row in reader]
    elif format_name == "jdeps":
        pairs = re.findall(r"^\s+(\S+)\s+->\s+(\S+)", text, re.M)
    else:
        raise ValueError(f"Unsupported dependency format: {format_name}")
    def admitted(name):
        return (any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
                and not any(fnmatchcase(name, pattern) for pattern in excludes))
    # Keep nested JVM classes. Collapsing '$' changes the graph and its denominator.
    return {(a, b): 1 for a, b in pairs if a != b and admitted(a) and admitted(b)}


def detekt(text, source_root):
    findings, seen = [], set()
    for run_index, run in enumerate(json.loads(text).get("runs", [])):
        for index, row in enumerate(run.get("results", [])):
            rule = row.get("ruleId", "").split(".")[-1]
            if rule not in RULES:
                continue
            location = row["locations"][0]["physicalLocation"]
            artifact = location["artifactLocation"]
            uri = artifact.get("uri")
            if uri is None and "index" in artifact:
                uri = run["artifacts"][artifact["index"]]["location"]["uri"]
            if uri is None:
                raise ValueError("SARIF finding has no resolvable artifact URI")
            # Relative URIs are resolved against the declared checkout, not a basename.
            path = relative_path(uri, source_root)
            region, message = location.get("region", {}), row.get("message", {}).get("text", "")
            identity = (rule, path, json.dumps(region, sort_keys=True), message)
            if identity in seen:
                continue
            seen.add(identity)
            pattern = RULES[rule]
            match = re.search(pattern, message) if pattern else None
            findings.append({"rule": rule, "file": path, "region": region,
                             "declaration": message, "value": int(match[1]) if match else None,
                             "suppressed": bool(row.get("suppressions")),
                             "record": f"complexity:runs/{run_index}/results/{index}"})
    return findings


def sizes(text, source_root):
    result = {}
    for language in json.loads(text):
        for row in language.get("Files", []):
            path = relative_path(row["Location"], source_root)
            result[path] = {key: int(row[key]) for key in ("Lines", "Code", "Comment", "Blank")}
            if any(value < 0 for value in result[path].values()):
                raise ValueError(f"Negative scc count for {path}")
    return result


def ratio(covered, total):
    if not 0 <= covered <= total:
        raise ValueError(f"Invalid coverage counters: {covered}/{total}")
    return {"covered": covered, "total": total, "value": covered / total if total else None,
            "status": "measured" if total else "not_applicable"}


def coverage(text, format_name, source_root, sources):
    rows, unmapped = {}, []
    if format_name == "coverage-csv":
        for row in csv.DictReader(io.StringIO(text)):
            path = relative_path(row["file"], source_root)
            if path in rows:
                raise ValueError(f"Duplicate coverage for {path}; supply one merged report")
            rows[path] = {kind: ratio(int(row[f"{kind}_covered"]), int(row[f"{kind}_total"]))
                          for kind in ("line", "branch")}
    elif format_name == "jacoco":
        lookup = defaultdict(list)
        for path, source in sources.items():
            lookup[source["package"].replace(".", "/"), PurePosixPath(path).name].append(path)
        for package in ET.fromstring(text).iter("package"):
            for sourcefile in package.findall("sourcefile"):
                key = (package.get("name", ""), sourcefile.get("name"))
                paths = lookup[key]
                if len(paths) != 1:
                    unmapped.append({"package": key[0], "sourcefile": key[1], "matches": paths})
                    continue
                path = paths[0]
                if path in rows:
                    raise ValueError(f"Duplicate coverage for {path}; merge execution data before XML export")
                counters = {counter.get("type"): counter for counter in sourcefile.findall("counter")}
                rows[path] = {}
                for kind in ("line", "branch"):
                    counter = counters.get(kind.upper())
                    if counter is None:
                        rows[path][kind] = {"covered": None, "total": None, "value": None, "status": "unknown"}
                    else:
                        covered, missed = int(counter.get("covered")), int(counter.get("missed"))
                        rows[path][kind] = ratio(covered, covered + missed)
    else:
        raise ValueError(f"Unsupported coverage format: {format_name}")
    return rows, unmapped


def source_description(text, language):
    # This heuristic is only for package identity and the pilot's explicit type counts.
    clean = re.sub(r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*', " ", text)
    package = re.search(r"(?m)^\s*package\s+([\w.]+)", clean)
    declarations = re.findall(r"\b(?:(abstract)\s+)?(class|interface|object)\s+\w+", clean) if language == ".kt" else []
    return {"package": package[1] if package else "", "types": len(declarations),
            "abstract": sum(bool(explicit) or kind == "interface" for explicit, kind in declarations)}


def class_source_file(data):
    """Read JVM SourceFile and this_class, avoiding FooKt/basename guessing."""
    stream = io.BytesIO(data)
    def read(size):
        value = stream.read(size)
        if len(value) != size:
            raise ValueError("Truncated JVM class file")
        return value
    def u2():
        return struct.unpack(">H", read(2))[0]
    def u4():
        return struct.unpack(">I", read(4))[0]
    if read(4) != b"\xca\xfe\xba\xbe":
        raise ValueError("Invalid JVM class header")
    read(4)
    pool, index, count = {}, 1, u2()
    widths = {3: 4, 4: 4, 5: 8, 6: 8, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
              15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
    while index < count:
        tag = read(1)[0]
        if tag == 1:
            pool[index] = read(u2()).decode("utf-8", errors="replace")
        elif tag == 7:
            pool[index] = u2()
        elif tag in widths:
            read(widths[tag])
        else:
            raise ValueError(f"Unsupported JVM constant tag {tag}")
        index += 2 if tag in (5, 6) else 1
    read(2)
    name = pool[pool[u2()]].replace("/", ".")
    read(2)
    read(2 * u2())
    def attributes():
        result = {}
        for _ in range(u2()):
            key, size = pool[u2()], u4()
            result[key] = read(size)
        return result
    for _ in range(2):
        for _ in range(u2()):
            read(6)
            attributes()
    source = attributes().get("SourceFile")
    return name, pool[struct.unpack(">H", source)[0]] if source else None


def type_counts(sources):
    counts = defaultdict(Counter)
    for source in sources.values():
        counts[source["package"]].update({key: source[key] for key in ("types", "abstract")})
    return dict(counts)
