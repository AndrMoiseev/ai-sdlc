"""ArchDRH-Re on a complete file population, followed by Decoupling Level.

Consumer -> supplier edges are the reverse of the influence arrows in ASE 2009.
Regions share the same terminal consumers. Connected regions become groups;
same-layer groups with equal nonempty supplier sets become conceptual groups.
Recursive control separation follows QoSA 2013 section 4. Leaves are flattened
once, then assigned their longest supplier-path layer. Isolates occupy the last
layer as singleton groups. This explicit convention is part of the profile.
"""

import math
from collections import defaultdict

from graph import components, reachable


def adjacency(nodes, edges):
    forward = {node: set() for node in nodes}
    reverse = {node: set() for node in nodes}
    for source, target in edges:
        if source != target:
            forward[source].add(target)
            reverse[target].add(source)
    return forward, reverse


def layers(groups, edges):
    owners = {node: index for index, group in enumerate(groups) for node in group}
    suppliers = {index: set() for index in range(len(groups))}
    for source, target in edges:
        left, right = owners[source], owners[target]
        if left != right:
            suppliers[left].add(right)
    result = {}
    while len(result) < len(groups):
        ready = [index for index in suppliers if index not in result and suppliers[index] <= result.keys()]
        if not ready:
            raise ValueError("DRH groups introduce a cycle between groups")
        for index in ready:
            result[index] = 1 + max((result[n] for n in suppliers[index]), default=0)
    return result, suppliers


def base_groups(nodes, edges):
    forward, reverse = adjacency(nodes, edges)
    groups = components(edges)
    present = {node for group in groups for node in group}
    groups.extend([[node] for node in sorted(set(nodes) - present)])
    owners = {node: index for index, group in enumerate(groups) for node in group}
    incoming = {owners[b] for a, b in edges if owners[a] != owners[b]}
    terminals = [group for index, group in enumerate(groups) if index not in incoming]
    signatures = {node: set() for node in nodes}
    for index, group in enumerate(terminals):
        for node in reachable(group[0], forward):
            signatures[node].add(index)
    # Independent regions with the same signature remain separate until step 2.
    pending, regions = set(nodes), []
    while pending:
        start = min(pending)
        group, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node in pending:
                pending.remove(node)
                group.add(node)
                stack.extend(n for n in forward[node] | reverse[node]
                             if n in pending and signatures[n] == signatures[start])
        regions.append(sorted(group))
    positions, suppliers = layers(regions, edges)
    conceptual = defaultdict(list)
    for index, group in enumerate(regions):
        key = (positions[index], tuple(sorted(suppliers[index]))) if suppliers[index] else ("root", index)
        conceptual[key].extend(group)
    return sorted((sorted(group) for group in conceptual.values()), key=lambda group: tuple(group))


def hierarchy(nodes, edges):
    nodes = set(nodes)
    edges = {(a, b) for a, b in edges if a != b and a in nodes and b in nodes}
    pending = base_groups(nodes, edges) if nodes else []
    leaves = []
    while pending:
        group = set(pending.pop())
        internal = {(a, b) for a, b in edges if a in group and b in group}
        count = len(group)
        if count < 2 or len(internal) < count or len(internal) > count ** 1.5:
            leaves.append(sorted(group))
            continue
        strongly_connected = components(internal)
        present = {node for part in strongly_connected for node in part}
        strongly_connected.extend([[node] for node in sorted(group - present)])
        owner = {node: index for index, part in enumerate(strongly_connected) for node in part}
        incoming = {owner[b] for a, b in internal if owner[a] != owner[b]}
        control = {node for index, part in enumerate(strongly_connected) if index not in incoming for node in part}
        rest = group - control
        if not rest:
            leaves.append(sorted(group))
            continue
        # Each condensed control component is an indivisible terminal group.
        leaves.extend(sorted(part) for part in strongly_connected if set(part) <= control)
        pending.extend(base_groups(rest, {(a, b) for a, b in internal if a in rest and b in rest}))
    leaves.sort(key=lambda group: tuple(group))
    positions, _ = layers(leaves, edges)
    connected = {node for edge in edges for node in edge}
    last = max(positions.values(), default=1)
    return sorted([{"files": group, "layer": last if not set(group) & connected else positions[index]}
                   for index, group in enumerate(leaves)], key=lambda row: (row["layer"], row["files"]))


def decoupling_level(nodes, edges, groups, small_group_files=5):
    nodes = set(nodes)
    if not nodes:
        return {"value": None, "status": "not_applicable", "groups": []}
    flat = [node for group in groups for node in group["files"]]
    if len(flat) != len(set(flat)) or set(flat) != nodes:
        raise ValueError("DRH must partition the complete file population")
    _, reverse = adjacency(nodes, edges)
    last = max(group["layer"] for group in groups)
    contributions = []
    for group in groups:
        size = len(group["files"])
        lower = {node for other in groups if other["layer"] > group["layer"] for node in other["files"]}
        if group["layer"] == last:
            factor = 1 if size <= small_group_files else math.log(small_group_files) / math.log(size)
            affected = set()
        else:
            affected = set().union(*(reachable(node, reverse) for node in group["files"])) & lower
            factor = 1 - len(affected) / len(lower)
        contributions.append({**group, "lower_files": len(lower), "affected_lower_files": len(affected),
                              "contribution": 100 * size / len(nodes) * factor})
    return {"value": math.fsum(row["contribution"] for row in contributions), "status": "known", "groups": contributions}


def structural_metrics(nodes, edges, small_group_files=5):
    nodes = set(nodes)
    edges = {(a, b) for a, b in edges if a != b and a in nodes and b in nodes}
    forward, reverse = adjacency(nodes, edges)
    cyclic = [part for part in components(edges) if len(part) > 1]
    visibility = {node: len(reachable(node, reverse)) / len(nodes) for node in sorted(nodes)}
    pairs = sum(len(reachable(node, forward)) for node in nodes)
    return {"node_count": len(nodes), "edge_count": len(edges),
            "propagation_cost": pairs / len(nodes) ** 2 if nodes else None,
            "reachable_pairs": pairs, "possible_pairs": len(nodes) ** 2,
            "cyclic_files": sum(map(len, cyclic)), "cyclic_file_fraction": sum(map(len, cyclic)) / len(nodes) if nodes else None,
            "largest_scc_size": max(map(len, cyclic), default=1 if nodes else 0), "cyclic_components": cyclic,
            "visibility_in": visibility,
            "decoupling_level": decoupling_level(nodes, edges, hierarchy(nodes, edges), small_group_files)}
