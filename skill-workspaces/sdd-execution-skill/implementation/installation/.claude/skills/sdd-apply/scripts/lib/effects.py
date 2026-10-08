"""Durable intents for operations whose effects cannot join the JSON transaction."""
import json
from .common import contained, digest, write_json, require


def intent(directory, state, event, operation, precondition):
    path = contained(directory, f"runs/{state['run_id']}/effects/{event['event_id']}.json")
    request = {"operation": operation, "task_id": event["task_id"], "event": event, "precondition": precondition}
    if path.exists():
        record = json.loads(path.read_text())
        require(record["request"]["event"] == event and record["request"]["operation"] == operation, "effect_conflict", "An effect ID cannot be reused")
        return path, record
    record = {"schema_version": 1, "request": request, "fingerprint": digest(request), "phase": "prepared", "result": None}
    write_json(path, record)
    return path, record


def observed(path, record, result):
    record.update(phase="observed", result=result)
    write_json(path, record)
    return result
