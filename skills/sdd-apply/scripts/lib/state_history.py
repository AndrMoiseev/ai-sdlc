"""Committed event chain with an immutable, content-addressed event-ID index."""
from .common import digest, require


def lookup(objects, index, event_id, depth=0):
    key = digest(event_id)
    while index:
        node = objects.get(index)
        if "event_id" in node:
            return objects.get(node["entry"]) if node["event_id"] == event_id else None
        index = node["children"].get(key[depth])
        depth += 1
        require(depth <= 64, "history_corrupt", "Invalid event index depth")
    return None


def insert(objects, index, event_id, entry, depth=0):
    if index is None:
        return objects.put({"event_id": event_id, "entry": entry})
    require(depth < 64, "history_corrupt", "Event ID hash collision")
    node = objects.get(index)
    if "event_id" in node:
        require(node["event_id"] != event_id, "event_conflict", "Event ID already committed")
        previous_key = digest(node["event_id"])
        children = {previous_key[depth]: index}
    else:
        children = dict(node["children"].items())
    key = digest(event_id)[depth]
    children[key] = insert(objects, children.get(key), event_id, entry, depth + 1)
    return objects.put({"children": children})


def append(objects, state, event, result):
    entry = objects.pack({"event_id": event["event_id"], "fingerprint": digest(event),
        "event": event, "revision": state["revision"], "previous": state["event_head"],
        "result": result, "time": state["updated_at"]}, root=True)
    reference = objects.put(entry)
    state["event_index"] = insert(objects, state["event_index"], event["event_id"], reference)
    state["event_head"] = reference


def entries(objects, state):
    """Newest first; used only by explicit history/audit operations."""
    current = state["event_head"]
    revision = state["revision"]
    while current:
        entry = objects.get(current)
        require(entry["revision"] == revision and revision > 0, "history_corrupt", "Event chain mismatch")
        yield entry
        current = entry["previous"]
        revision -= 1
    require(revision == 0, "history_corrupt", "History length mismatch")


def audit(objects, state):
    seen, ids = set(), set()
    for entry in entries(objects, state):
        ident = entry["event_id"]
        require(ident not in ids and entry["event"]["event_id"] == ident
                and entry["fingerprint"] == digest(entry["event"]), "history_corrupt", "Invalid event identity")
        require(lookup(objects, state["event_index"], ident) == entry,
                "history_corrupt", "Event index disagrees with chain")
        ids.add(ident)
        objects.audit(entry, seen)
    # Every index leaf must belong to the committed chain, including after a
    # failed write followed by a different event at the same revision.
    pending = [state["event_index"]] if state["event_index"] else []
    indexed = set()
    while pending:
        node = objects.get(pending.pop())
        if "event_id" in node:
            require(node["event_id"] not in indexed, "history_corrupt", "Duplicate index leaf")
            indexed.add(node["event_id"])
        else:
            pending.extend(node["children"].values())
    require(indexed == ids, "history_corrupt", "Uncommitted event in index")
    return len(ids)
