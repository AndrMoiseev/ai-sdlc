"""Select evidence for one diagnosis from a saved architecture audit."""

from audit_configuration import project_path
from candidate_groups import selection_reference
from measurements import CATALOG, read_jsonl, read_keyed_rows, reference, resolve_measurements


def group_evidence(collection, directory, identity):
    def selection(name, field, keys):
        path = f"selections/{name}.jsonl"
        descriptor = collection["selections"][name]
        if descriptor["status"] != "complete" or descriptor["path"] != path:
            raise ValueError(f"Selection is unavailable: {name}")
        return read_keyed_rows(directory, path, [field], keys)

    group, = selection("candidate-groups", "group", [{"group": identity}])
    signal_keys = []
    for ref in group["signals"]:
        if ref["path"] != "selections/signals.jsonl":
            raise ValueError(f"Invalid signal reference in {identity}: {ref}")
        signal_keys.append(ref["key"])
    signals = selection("signals", "signal", signal_keys)
    refs = [ref for signal in signals for ref in signal["references"]]
    return {"origin": selection_reference("candidate-groups", "group", identity),
            "candidate_group": group, "signals": signals,
            "measurements": [{"reference": reference(name, row), "row": row}
                             for name, row in resolve_measurements(refs, collection, directory)]}


def metric_rows(collection, directory, name):
    """Optional inputs can be unavailable in a completed focused collection."""
    if collection["outputs"][name]["status"] == "complete":
        yield from read_jsonl(directory, CATALOG[name]["path"])


def file_evidence(files, collection, directory):
    measurements = []
    outcomes = {}
    for name in ("source-files/file", "change-frequency/file", "line-coverage/file"):
        outcomes[name] = collection["outputs"][name]
        for row in metric_rows(collection, directory, name):
            if row["file"] in files:
                measurements.append({"reference": reference(name, row), "row": row})
    return {"files": sorted(files), "outputs": outcomes, "measurements": measurements}


def joint_changes(files, commits, maximum_changeset_size):
    if len(files) != 2:
        raise ValueError("Co-change needs two distinct project-relative files")
    result = []
    for commit in commits:
        changes = [change for change in commit["changes"] if change["file"] in files]
        if len(changes) == 2:
            result.append({"reference": reference("changes/commit", commit), "date": commit["date"],
                           "changeset_size": commit["changeset_size"], "changes": changes,
                           "included_in_coupling": commit["changeset_size"] <= maximum_changeset_size})
    return result


def class_dependencies(files, mappings, edges):
    by_class = {row["class"]: row["file"] for row in mappings}
    unmapped_classes = set()
    result = []
    for edge in edges:
        consumer, supplier = edge["from"], edge["to"]
        consumer_file, supplier_file = by_class.get(consumer), by_class.get(supplier)
        for name in (consumer, supplier):
            if name not in by_class:
                unmapped_classes.add(name)
        if consumer_file in files or supplier_file in files:
            result.append({"reference": reference("dependencies/class", edge),
                           "from_file": consumer_file, "to_file": supplier_file})
    return {"edges": result, "files_without_mapped_classes": sorted(files - set(by_class.values())),
            "unmapped_graph_class_count": len(unmapped_classes)}


def candidate_evidence(collection, directory, args):
    if collection["status"] != "complete":
        raise ValueError("Evidence requires a completed collection")
    if args.group is not None:
        return group_evidence(collection, directory, args.group)
    files = {project_path(path, "evidence file") for path in (args.files or args.co_change or args.dependencies)}
    if args.files:
        return file_evidence(files, collection, directory)
    if args.co_change:
        name = "changes/commit"
        limit = collection["analysis_policy"]["measurements"]["history"]["maximum_changeset_size"]
        return {"files": sorted(files), "output": collection["outputs"][name], "maximum_changeset_size": limit,
                "commits": joint_changes(files, metric_rows(collection, directory, name), limit)}
    names = ("class-files/class", "dependencies/class")
    mappings = metric_rows(collection, directory, "class-files/class")
    edges = metric_rows(collection, directory, "dependencies/class")
    return {"files": sorted(files), "outputs": {name: collection["outputs"][name] for name in names},
            "mapping_gap_count": sum(gap.get("artifact") == "mapping" for gap in collection["gaps"]),
            **class_dependencies(files, mappings, edges)}
