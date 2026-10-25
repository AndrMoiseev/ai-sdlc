"""Immutable JSON objects and selective loading for execution state.

References are internal to the stored format. Reducers see ordinary mapping/list
values; unopened references survive copies and saves without being hydrated.
"""
from copy import deepcopy
from contextlib import contextmanager
import json
import re

from . import artifact_storage as artifacts
from .common import Rejected, digest, require


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


class StateObjects:
    def __init__(self, directory):
        self.directory = directory
        self.verified = {}
        self._reads = None

    def validate_reference(self, reference):
        require(isinstance(reference, dict) and set(reference) == {"path", "sha256", "bytes", "kind"}
                and isinstance(reference["sha256"], str)
                and re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])
                and reference["path"] == f"objects/{reference['sha256'][:2]}/{reference['sha256']}.json"
                and type(reference["bytes"]) is int and reference["bytes"] >= 0
                and reference["kind"] in {"object", "array", "string"},
                "object_reference", "Invalid execution object reference")

    def path(self, reference):
        self.validate_reference(reference)
        return artifacts.contained(self.directory, reference["path"])

    def put(self, value, raw=None):
        raw = encoded(value) if raw is None else raw
        sha = digest(raw)
        kind = "object" if isinstance(value, dict) else "array" if isinstance(value, list) else "string"
        reference = {"path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha, "bytes": len(raw), "kind": kind}
        if sha not in self.verified:
            path = self.path(reference)
            if artifacts.exists(path):
                require(artifacts.read_bytes(path) == raw, "object_corrupt", reference["path"])
            else:
                artifacts.write(path, raw)
            self.verified[sha] = raw
        return reference

    def raw(self, reference):
        self.validate_reference(reference)
        key = (reference["path"], reference["sha256"], reference["bytes"], reference["kind"])
        if self._reads is not None and key in self._reads:
            return self._reads[key]
        path = artifacts.contained(self.directory, reference["path"])
        try:
            raw = artifacts.read_bytes(path)
        except FileNotFoundError as exc:
            raise Rejected("object_missing", "Execution object is missing: " + reference["path"]) from exc
        require(len(raw) == reference["bytes"] and digest(raw) == reference["sha256"],
                "object_corrupt", reference["path"])
        if self._reads is not None:
            self._reads[key] = raw
        return raw

    @contextmanager
    def cached_reads(self):
        """Verify each immutable object once in one audit, never across operations."""
        previous, self._reads = self._reads, {}
        try:
            yield
        finally:
            self._reads = previous

    def get(self, reference):
        value = json.loads(self.raw(reference))
        expected = {"object": dict, "array": list, "string": str}[reference["kind"]]
        require(type(value) is expected, "object_corrupt", "Object type mismatch")
        return self.open(value)

    def open(self, value):
        if isinstance(value, LazyState):
            return value
        if isinstance(value, dict):
            if set(value) == {"$object"}:
                return self.get(value["$object"])
            return LazyState(value, self)
        if isinstance(value, list):
            # Elements are usually small evidence records; their large fields
            # remain references inside LazyState until explicitly accessed.
            for index, item in enumerate(value):
                value[index] = self.open(item)
            return value
        return value

    def pack(self, value, field=None, root=False):
        return self._pack(value, field, root)[0]

    def _pack(self, value, field=None, root=False):
        """Compute JSON sizes bottom-up instead of re-encoding every subtree."""
        if isinstance(value, dict):
            if set(value) == {"$object"}:
                self.path(value["$object"])
                result = {"$object": dict(value["$object"])}
                return result, len(encoded(result))
            pairs = dict.items(value) if isinstance(value, LazyState) else value.items()
            result, size = {}, 2
            for key, item in pairs:
                packed, length = self._pack(item, key)
                key_size = len(json.encoder.encode_basestring_ascii(key)) if isinstance(key, str) else len(encoded({key: None})) - 7
                size += key_size + 1 + length + bool(result)
                result[key] = packed
        elif isinstance(value, list):
            result, size = [], 2
            for item in value:
                packed, length = self._pack(item)
                size += length + bool(result)
                result.append(packed)
        else:
            result = value
            if isinstance(value, str):
                size = len(json.encoder.encode_basestring_ascii(value))
            elif value is None or value is True:
                size = 4
            elif value is False:
                size = 5
            elif isinstance(value, int):
                size = len(str(value))
            else:
                size = len(encoded(value))
        # Keep control fields inline. Collections with an execution-lifetime
        # history and source snapshots always live outside the current manifest.
        external = field in {"prior_result", "baseline", "start_snapshot", "freeze_base",
            "snapshot", "working_patch", "index_patch", "evidence", "reviews", "commits",
            "repair_cycles", "budget_decisions", "worktree_history", "check_registry", "roles"}
        external = external or field == "source" and isinstance(result, dict) and {"files", "digest"} <= result.keys()
        control = field in {"basis", "tasks"} or isinstance(field, str) and field.startswith("TASK-")
        if not root and not control and isinstance(result, (dict, list, str)) and result and (external or size > 4096):
            result = {"$object": self.put(result)}
            size = len(encoded(result))
        return result, size

    def audit(self, value, seen=None):
        seen = set() if seen is None else seen
        if isinstance(value, dict):
            if set(value) == {"$object"}:
                ref = value["$object"]
                self.path(ref)
                if ref["sha256"] not in seen:
                    seen.add(ref["sha256"])
                    self.audit(self.get(ref), seen)
            else:
                pairs = dict.values(value) if isinstance(value, LazyState) else value.values()
                for item in pairs:
                    self.audit(item, seen)
        elif isinstance(value, list):
            for item in value:
                self.audit(item, seen)
        return seen


class LazyState(dict):
    """A mutable mapping whose still-encoded values copy without disk reads."""
    def __init__(self, value, objects):
        super().__init__(value)
        self.objects = objects

    @property
    def manifest(self):
        """Decode the verified manifest only when its public view is requested."""
        return json.loads(self.manifest_bytes)

    def __getitem__(self, key):
        value = dict.__getitem__(self, key)
        if isinstance(value, LazyState) or not isinstance(value, (dict, list)):
            return value
        value = self.objects.open(value)
        dict.__setitem__(self, key, value)
        return value

    def get(self, key, default=None):
        return self[key] if key in self else default

    def items(self):
        return ((key, self[key]) for key in self)

    def values(self):
        return (self[key] for key in self)

    def pop(self, key, *default):
        if key not in self:
            return dict.pop(self, key, *default)
        value = self[key]
        dict.__delitem__(self, key)
        return value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __deepcopy__(self, memo):
        result = LazyState({}, self.objects)
        memo[id(self)] = result
        for key, value in dict.items(self):
            result[key] = deepcopy(value, memo)
        return result

    def __eq__(self, other):
        if not isinstance(other, dict) or self.keys() != other.keys():
            return False
        return all(self[key] == self.objects.open(other[key]) for key in self)

    def __ne__(self, other):
        return not self == other
