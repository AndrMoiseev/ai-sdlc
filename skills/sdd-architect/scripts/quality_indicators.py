"""Project and module indicators; all arithmetic operates on qualified complete inputs."""

import bisect
import heapq
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
import xml.etree.ElementTree as ET

from design_rule_hierarchy import structural_metrics
from graph import module_for
from inputs import relative_path


def score(excess):
    return 100 / (1 + excess)


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def fraction(numerator, denominator):
    return {"value": numerator / denominator if denominator else None, "numerator": numerator,
            "denominator": denominator, "status": "known" if denominator else "not_applicable"}


def qualify_kotlin(value, sources):
    from detekt_runtime import plugin_metadata, select_plugin
    metadata = plugin_metadata()
    if (value.get("format") != "kotlin-measurements" or value.get("version") != metadata["schema_version"]
            or value.get("complete") is not True
            or value.get("measurement_profile") != metadata["measurement_profile"]
            or not isinstance(value.get("tool_version"), str)):
        raise ValueError("Kotlin measurements are missing or incomplete; run detekt with the bundled measurement plugin")
    select_plugin(value["tool_version"])
    rows = value.get("files", [])
    files = {row["file"]: row for row in rows}
    expected = {path for path, source in sources.items() if source["language"] == ".kt"}
    if len(files) != len(rows) or set(files) != expected:
        raise ValueError("Kotlin measurements must cover each production Kotlin file exactly once")
    for path, row in files.items():
        if row["package"] != sources[path]["package"]:
            raise ValueError(f"Kotlin package does not match the source inventory: {path}")
        end = 0
        for token in row["tokens"]:
            if not (type(token["start"]) is int and type(token["end"]) is int and end <= token["start"] < token["end"]):
                raise ValueError(f"Invalid token positions: {path}")
            if not token["type"] or not token["text"]:
                raise ValueError(f"Empty code token: {path}")
            end = token["end"]
        for function in row["functions"]:
            if type(function["cognitive_complexity"]) is not int or function["cognitive_complexity"] < 0:
                raise ValueError(f"Missing cognitive complexity: {path}")
            if not 0 <= function["start"] < function["end"] or type(function["nested"]) is not bool:
                raise ValueError(f"Invalid function range: {path}")
        for container in row["containers"]:
            if container["kind"] not in {"function", "class"} or not 0 <= container["start"] < container["end"]:
                raise ValueError(f"Invalid size container: {path}")
    return files


def maintainability(files, parameters):
    total_tokens = cognitive_weight = complex_tokens = 0
    cognitive_excess = size_excess = 0.0
    functions = []
    largest = []
    for path, row in sorted(files.items()):
        tokens = row["tokens"]
        starts = [token["start"] for token in tokens]
        total_tokens += len(tokens)
        def bounds(container):
            return bisect.bisect_left(starts, container["start"]), bisect.bisect_left(starts, container["end"])
        for function in row["functions"]:
            if function["nested"]:
                continue
            start, end = bounds(function)
            weight = end - start
            complexity = function["cognitive_complexity"]
            excess = weight * max(0, complexity / parameters["cognitive_complexity"] - 1)
            cognitive_weight += weight
            cognitive_excess += excess
            complex_tokens += weight if complexity > parameters["cognitive_complexity"] else 0
            functions.append({"file": path, **function, "tokens": weight, "excess": excess})
        events = defaultdict(list)
        file_penalty = max(0, len(tokens) / parameters["file_tokens"] - 1)
        for container in row["containers"]:
            start, end = bounds(container)
            penalty = max(0, (end - start) / parameters[container["kind"] + "_tokens"] - 1)
            if penalty:
                events[start].append((-penalty, end))
        active = []
        contribution = 0.0
        for position in range(len(tokens)):
            for entry in events.get(position, []):
                heapq.heappush(active, entry)
            while active and active[0][1] <= position:
                heapq.heappop(active)
            contribution += max(file_penalty, -active[0][0] if active else 0)
        size_excess += contribution
        largest.append({"file": path, "tokens": len(tokens), "size_excess": contribution})
    cognitive_score = score(cognitive_excess / cognitive_weight) if cognitive_weight else None
    size_score = score(size_excess / total_tokens) if total_tokens else None
    weighted_p95, accumulated = None, 0
    for function in sorted(functions, key=lambda row: row["cognitive_complexity"]):
        accumulated += function["tokens"]
        if cognitive_weight and accumulated >= .95 * cognitive_weight:
            weighted_p95 = function["cognitive_complexity"]
            break
    return {"value": math.sqrt(cognitive_score * size_score) if cognitive_score is not None and size_score is not None else None,
            "status": "known" if cognitive_score is not None and size_score is not None else "not_applicable",
            "cognitive_score": cognitive_score, "size_score": size_score, "tokens": total_tokens,
            "function_count": len(functions), "function_tokens": cognitive_weight, "outside_function_tokens": total_tokens - cognitive_weight,
            "cognitive_excess": cognitive_excess, "size_excess": size_excess,
            "maximum_cognitive_complexity": max((row["cognitive_complexity"] for row in functions), default=None),
            "weighted_p95_cognitive_complexity": weighted_p95,
            "complex_tokens": complex_tokens, "complex_token_fraction": fraction(complex_tokens, cognitive_weight),
            "largest_cognitive_contributions": sorted(functions, key=lambda row: (-row["excess"], row["file"], row["start"]))[:10],
            "largest_size_contributions": sorted(largest, key=lambda row: (-row["size_excess"], row["file"]))[:10]}


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def duplication(files, minimum, owners):
    """Exact fixed-length windows suffice for the union of all clone positions.

    A rolling hash selects candidates; complete token tuples verify every match.
    Union of matching minimum-length windows equals the union of extended clones.
    Same-file partners must be nonoverlapping. No pairwise clone enumeration.
    """
    identifiers, sequences = {}, {}
    for path, row in sorted(files.items()):
        sequence = []
        for token in row["tokens"]:
            key = (token["type"], token["text"])
            sequence.append(identifiers.setdefault(key, len(identifiers) + 1))
        sequences[path] = sequence
    buckets = defaultdict(list)
    mask, base = (1 << 64) - 1, 1000003
    power = pow(base, minimum - 1, 1 << 64)
    for path, sequence in sequences.items():
        current = 0
        for index, token in enumerate(sequence):
            if index >= minimum:
                current = (current - sequence[index - minimum] * power) & mask
            current = (current * base + token) & mask
            if index + 1 >= minimum:
                start = index + 1 - minimum
                for occurrences in buckets[current]:
                    other_path, other_start = occurrences[0]
                    if sequences[other_path][other_start:other_start + minimum] == sequence[start:index + 1]:
                        occurrences.append((path, start))
                        break
                else:
                    buckets[current].append([(path, start)])
    intervals, boundary = defaultdict(list), defaultdict(list)
    for bucket in buckets.values():
        for occurrences in bucket:
            if len(occurrences) < 2:
                continue
            paths = {path for path, _ in occurrences}
            modules = {owners[path] for path in paths}
            first, last = occurrences[0][1], occurrences[-1][1]
            for path, start in occurrences:
                if len(paths) > 1 or max(start - first, last - start) >= minimum:
                    intervals[path].append((start, start + minimum))
                    if len(modules) > 1:
                        boundary[path].append((start, start + minimum))
    def summarize(values):
        result = {}
        for path in files:
            merged = merge_intervals(values[path])
            result[path] = {"tokens": sum(end - start for start, end in merged), "intervals": merged}
        return result
    return summarize(intervals), summarize(boundary)


def coverage_methods(text, sources, mappings):
    root = ET.fromstring(text)
    if root.tag != "report":
        raise ValueError("Coverage input must be a complete JaCoCo XML report")
    methods, lines, classes = {}, {}, set()
    source_lookup = defaultdict(list)
    for path, source in sources.items():
        source_lookup[source["package"].replace(".", "/"), path.rsplit("/", 1)[-1]].append(path)
    for package in root.iter("package"):
        for source in package.findall("sourcefile"):
            paths = source_lookup.get((package.get("name", ""), source.get("name")), [])
            if len(paths) > 1:
                raise ValueError("Ambiguous JaCoCo source file; provide a single selected source-set report")
            if not paths:
                continue
            path = paths[0]
            for line in source.findall("line"):
                key = (path, int(line.attrib["nr"]))
                if key in lines:
                    raise ValueError("Duplicate JaCoCo source line; merge execution data before XML export")
                covered, missed = int(line.attrib["ci"]), int(line.attrib["mi"])
                if key[1] < 1 or min(covered, missed) < 0 or covered + missed == 0:
                    raise ValueError("Invalid JaCoCo executable source line")
                lines[key] = covered > 0
        for clazz in package.findall("class"):
            name = clazz.attrib["name"].replace("/", ".")
            path = mappings.get(name)
            if path not in sources:
                continue
            if name in classes:
                raise ValueError("Duplicate JaCoCo class; merge execution data before XML export")
            classes.add(name)
            for method in clazz.findall("method"):
                counters = {}
                for counter in method.findall("counter"):
                    kind = counter.attrib["type"]
                    if kind in counters:
                        raise ValueError("Duplicate JaCoCo method counter")
                    covered, missed = int(counter.attrib["covered"]), int(counter.attrib["missed"])
                    if min(covered, missed) < 0:
                        raise ValueError("Negative JaCoCo method counter")
                    counters[kind] = (covered, covered + missed)
                if "INSTRUCTION" not in counters or "COMPLEXITY" not in counters:
                    raise ValueError(f"Incomplete JaCoCo method counters: {name}.{method.get('name')}")
                instructions, total_instructions = counters["INSTRUCTION"]
                complexity = counters["COMPLEXITY"][1]
                if not total_instructions or not complexity:
                    raise ValueError("JaCoCo executable method has zero instructions or complexity")
                # JaCoCo's XML exporter omits zero-total counters, including BRANCH.
                branches, total_branches = counters.get("BRANCH", (0, 0))
                execution = min(instructions / total_instructions, branches / total_branches) if total_branches else instructions / total_instructions
                excess = complexity ** 2 * (1 - execution) ** 3
                key = (name, method.attrib["name"], method.attrib["desc"])
                if key in methods:
                    raise ValueError("Duplicate JaCoCo method identity")
                methods[key] = {"class": name, "method": key[1], "descriptor": key[2], "file": path,
                                "instructions": instructions, "total_instructions": total_instructions,
                                "branches": branches, "total_branches": total_branches,
                                "complexity": complexity, "crap_exec": complexity + excess, "excess": excess}
    expected = {name for name, path in mappings.items() if path in sources}
    if expected - classes:
        raise ValueError("JaCoCo omits mapped production classes: " + ", ".join(sorted(expected - classes)[:10]))
    missing_lines = {row["file"] for row in methods.values()} - {path for path, _ in lines}
    if missing_lines:
        raise ValueError("JaCoCo omits executable source lines: " + ", ".join(sorted(missing_lines)[:10]))
    return list(methods.values()), lines


def coverage_summary(paths, methods, lines, tokens):
    selected = [row for row in methods if row["file"] in paths]
    excess = math.fsum(row["excess"] for row in selected)
    squared = sum(row["complexity"] ** 2 for row in selected)
    source_lines = [covered for (path, _), covered in lines.items() if path in paths]
    return {"method_count": len(selected),
            "branch": fraction(sum(row["branches"] for row in selected), sum(row["total_branches"] for row in selected)),
            "instruction": fraction(sum(row["instructions"] for row in selected), sum(row["total_instructions"] for row in selected)),
            "line": fraction(sum(source_lines), len(source_lines)),
            "total_crap": math.fsum(row["crap_exec"] for row in selected), "total_excess": excess,
            "excess_density": 1000 * excess / tokens if tokens else None,
            "E_CRAP": 100 * excess / squared if squared else None,
            "p95_crap_exec": percentile([row["crap_exec"] for row in selected]),
            "largest_excess": sorted(selected, key=lambda row: (-row["excess"], row["class"], row["method"], row["descriptor"]))[:10]}


def history_summary(paths, commits, files, parameters, as_of):
    cutoff = as_of - timedelta(days=parameters["history_days"])
    revisions, support = Counter(), Counter()
    excluded = observations = 0
    for commit in commits:
        if not cutoff <= date.fromisoformat(commit["date"]) <= as_of:
            continue
        production = set(commit["changes"]) & set(files)
        if commit.get("production_files", len(production)) > parameters["history_maximum_files"]:
            excluded += 1
            continue
        selected = sorted(production & paths)
        observations += bool(selected)
        revisions.update(selected)
        for index, left in enumerate(selected):
            for right in selected[index + 1:]:
                support[left, right] += 1
    pairs = []
    involved = set()
    for (left, right), shared in support.items():
        average = (revisions[left] + revisions[right]) / 2
        degree = shared / average
        if shared >= parameters["history_minimum_shared"] and average >= parameters["history_minimum_average"] and degree >= parameters["history_minimum_coupling"]:
            pairs.append({"left": left, "right": right, "shared": shared, "coupling": degree})
            involved.update((left, right))
    tokens = sum(len(files[path]["tokens"]) for path in paths)
    exposed = sum(len(files[path]["tokens"]) for path in involved)
    return {"since": cutoff.isoformat(), "until": as_of.isoformat(), "observations": observations,
            "status": "known" if observations >= parameters["history_minimum_shared"] else "limited",
            "excluded_large_commits": excluded, "coupled_files": len(involved), "coupled_tokens": exposed,
            "coupled_token_fraction": fraction(exposed, tokens), "pairs": sorted(pairs, key=lambda row: (-row["coupling"], row["left"], row["right"]))}


def indicators(files, edges, modules, methods, lines, commits, parameters, as_of):
    owners = {path: module_for(row["package"], modules) for path, row in files.items()}
    unassigned = sorted(path for path, owner in owners.items() if owner is None)
    if unassigned:
        raise ValueError("Assign production packages to architectural modules before auditing: " + ", ".join(unassigned[:10]))
    if not modules:
        raise ValueError("Declare architectural modules before auditing")
    project_duplicates, boundary_duplicates = duplication(files, parameters["clone_tokens"], owners)
    def calculate(paths, duplicates):
        selected = {path: files[path] for path in paths}
        local = maintainability(selected, parameters)
        structure = structural_metrics(paths, edges, parameters["small_group_files"])
        repeated = sum(duplicates[path]["tokens"] for path in paths)
        tokens = local["tokens"]
        duplication_score = score(repeated / tokens / parameters["duplication_reference"]) if tokens else None
        components = (structure["decoupling_level"]["value"], local["value"], duplication_score)
        return {"files": len(paths), "tokens": tokens,
                "Q": math.prod(components) ** (1 / 3) if all(value is not None for value in components) else None,
                "D": components[0], "L": components[1], "U": components[2],
                "status": "known" if all(value is not None for value in components) else "not_applicable",
                "structure": structure, "local_maintainability": local,
                "duplication": {"fraction": fraction(repeated, tokens), "tokens": repeated,
                                "files": {path: duplicates[path] for path in sorted(paths)}},
                "coverage": coverage_summary(paths, methods, lines, tokens),
                "history": history_summary(paths, commits, files, parameters, as_of)}
    project = calculate(set(files), project_duplicates)
    project_cyclic = {path for group in project["structure"]["cyclic_components"] for path in group}
    cross_coupled = {path for pair in project["history"]["pairs"]
                     if owners[pair["left"]] != owners[pair["right"]] for path in (pair["left"], pair["right"])}
    by_module = {}
    for module in sorted(modules):
        paths = {path for path, owner in owners.items() if owner == module}
        duplicates, _ = duplication({path: files[path] for path in paths}, parameters["clone_tokens"], owners)
        value = by_module[module] = calculate(paths, duplicates)
        value["boundary"] = {"incoming_edges": sum(a not in paths and b in paths for a, b in edges),
                             "outgoing_edges": sum(a in paths and b not in paths for a, b in edges),
                             "project_cyclic_files": len(paths & project_cyclic),
                             "cross_module_coupled_tokens": sum(len(files[path]["tokens"]) for path in paths & cross_coupled),
                             "cross_module_duplicate_tokens": sum(boundary_duplicates[path]["tokens"] for path in paths),
                             "project_duplicate_tokens": sum(project_duplicates[path]["tokens"] for path in paths)}
    return {"project": project, "modules": by_module}
