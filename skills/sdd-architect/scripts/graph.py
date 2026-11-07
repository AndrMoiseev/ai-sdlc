"""Dependency views. Edges point from a consumer to its supplier."""

from collections import Counter, defaultdict


def module_for(package, modules):
    matches = [(len(prefix), name) for name, prefixes in modules.items()
               for prefix in prefixes if package == prefix or package.startswith(prefix + ".")]
    if not matches:
        return None
    length = max(size for size, _ in matches)
    owners = {name for size, name in matches if size == length}
    if len(owners) != 1:
        raise ValueError(f"Ambiguous module ownership for {package}: {sorted(owners)}")
    return owners.pop()


def package_of(name):
    return name.rpartition(".")[0]


def aggregate(edges, key):
    result = Counter()
    for (source, target), weight in edges.items():
        left, right = key(source), key(target)
        if left is not None and right is not None and left != right:
            result[left, right] += weight
    return dict(sorted(result.items()))


def adjacency(edges):
    forward, reverse = defaultdict(set), defaultdict(set)
    for source, target in edges:
        forward[source].add(target)
        forward[target]
        reverse[target].add(source)
        reverse[source]
    return forward, reverse


def reachable(start, graph):
    seen, pending = {start}, [start]
    while pending:
        for node in graph[pending.pop()]:
            if node not in seen:
                seen.add(node)
                pending.append(node)
    return seen


def components(edges):
    """Iterative Kosaraju: also works on long graphs beyond Python recursion depth."""
    forward, reverse = adjacency(edges)
    visited, finish = set(), []
    for start in sorted(forward):
        if start in visited:
            continue
        stack = [(start, False)]
        while stack:
            node, done = stack.pop()
            if done:
                finish.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((n, False) for n in sorted(forward[node], reverse=True)
                             if n not in visited)
    visited, result = set(), []
    for start in reversed(finish):
        if start in visited:
            continue
        group, pending = set(), [start]
        while pending:
            node = pending.pop()
            if node not in visited:
                visited.add(node)
                group.add(node)
                pending.extend(reverse[node] - visited)
        result.append(sorted(group))
    return sorted(result, key=lambda group: (-len(group), group))


def graph_view(edges):
    edges = {(a, b): w for (a, b), w in edges.items() if a != b}
    forward, reverse = adjacency(edges)
    count = len(forward)
    cyclic = [group for group in components(edges) if len(group) > 1]
    membership = {node: index for index, group in enumerate(cyclic) for node in group}
    cycle_edges = [(a, b, w) for (a, b), w in sorted(edges.items())
                   if a in membership and membership.get(b) == membership[a]]
    nodes = {}
    for node in sorted(forward):
        incoming, outgoing = len(reachable(node, reverse)), len(reachable(node, forward))
        nodes[node] = {"fan_in": len(reverse[node]), "fan_out": len(forward[node]),
                       "incoming_weight": sum(edges[n, node] for n in reverse[node]),
                       "outgoing_weight": sum(edges[node, n] for n in forward[node]),
                       "reachable_in": incoming, "reachable_out": outgoing,
                       "visibility_in": incoming / count, "visibility_out": outgoing / count}
    numerator = sum(node["reachable_out"] for node in nodes.values())
    # The denominator intentionally contains only edge endpoints, including the diagonal.
    return {"node_count": count, "edge_count": len(edges), "nodes": nodes,
            "cyclic_components": cyclic, "cyclic_edges": cycle_edges,
            "propagation_cost": {"numerator": numerator, "denominator": count * count,
                                 "value": numerator / count**2 if count else None},
            "layers": dependency_layers(edges)}


def dependency_layers(edges):
    remaining = set(node for edge in edges for node in edge)
    result = []
    while remaining:
        current = {(a, b): w for (a, b), w in edges.items() if a in remaining and b in remaining}
        outgoing = {a for a, _ in current}
        incoming = {b for _, b in current}
        selected = sorted(remaining - outgoing)
        kind = "no_suppliers"
        if not selected:
            selected, kind = sorted(remaining - incoming), "no_consumers"
        if not selected:
            selected, kind = components(current)[0], "cyclic_core"
        result.append({"kind": kind, "nodes": selected})
        remaining.difference_update(selected)
    return result


def module_views(package_edges, modules, type_counts):
    internal, boundary = Counter(), Counter()
    external = defaultdict(Counter)
    incoming, outgoing = Counter(), Counter()
    for (source, target), weight in package_edges.items():
        left, right = module_for(source, modules), module_for(target, modules)
        outgoing[source] += weight
        incoming[target] += weight
        if left is not None and left == right:
            internal[left] += weight
        else:
            if left is not None:
                boundary[left] += weight
            if right is not None:
                boundary[right] += weight
            # Unknown packages are not a single architectural module.
            external[source][right] += weight
            external[target][left] += weight
    cohesion = {}
    for module in sorted(modules):
        total = internal[module] + boundary[module]
        cohesion[module] = {"internal": internal[module], "boundary": boundary[module],
                            "value": internal[module] / total if total else None}
    affinity = {}
    for package, weights in sorted(external.items()):
        total = sum(weights.values())
        declared = sum(weight for owner, weight in weights.items() if owner is not None)
        shares = {owner: weight / declared for owner, weight in sorted(weights.items(), key=lambda p: str(p[0]))
                  if owner is not None and declared}
        ranked = sorted(shares.values(), reverse=True)
        category = "grey" if not declared or declared / total < .34 else (
            "orphan" if ranked[0] < .25 else "bridge" if len(ranked) > 1 and ranked[1] >= .33 else "leading_external")
        affinity[package] = {"external_weight": total, "declared_weight": declared,
                             "declared_fraction": declared / total, "shares": shares, "category": category}
    martin = {}
    for package, counts in sorted(type_counts.items()):
        total, abstract = counts["types"], counts["abstract"]
        if total < 5 or not incoming[package] + outgoing[package]:
            continue
        instability = outgoing[package] / (incoming[package] + outgoing[package])
        abstractness = abstract / total
        martin[package] = {"Ca": incoming[package], "Ce": outgoing[package],
                           "types": total, "abstract_types": abstract, "I": instability,
                           "A": abstractness, "D": abs(abstractness + instability - 1),
                           "basis": "source declaration heuristic; explicit abstract/interface only"}
    return {"cohesion": cohesion, "external_affinity": affinity, "martin": martin}
