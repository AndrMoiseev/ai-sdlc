"""The only reader of numeric defaults and project overrides; calculations receive a resolved policy."""

import json
import math
from copy import deepcopy
from pathlib import Path


ASSETS = Path(__file__).resolve().parents[1] / "assets"
PROJECT_POLICY = Path(".sdd") / "architect" / "analysis-policy.json"


def read_json(path):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate policy key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=object_pairs)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def validate_policy(value, *, complete=False, schema=None):
    """Validate the bundled schema's object/numeric subset, then cross-field invariants.

    The same schema accepts full defaults and partial project overrides. Completeness
    is required separately for defaults and resolved audit values.
    """
    schema = schema if schema is not None else read_json(ASSETS / "analysis-policy.schema.json")

    def visit(current, rule, path):
        kind = rule["type"]
        if kind == "object":
            if not isinstance(current, dict):
                raise ValueError(f"{path}: expected object")
            properties = rule["properties"]
            unknown = set(current) - properties.keys()
            if unknown:
                raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
            if complete and set(current) != set(properties):
                raise ValueError(f"{path}: missing keys {sorted(set(properties) - current.keys())}")
            return {name: visit(item, properties[name], f"{path}.{name}") for name, item in current.items()}
        if type(current) not in (int, float) or (type(current) is float and not math.isfinite(current)):
            raise ValueError(f"{path}: expected finite {kind}")
        if kind == "integer":
            if current != int(current):
                raise ValueError(f"{path}: expected finite integer")
            current = int(current)
        for keyword, invalid in (
            ("minimum", lambda limit: current < limit),
            ("maximum", lambda limit: current > limit),
            ("exclusiveMinimum", lambda limit: current <= limit),
            ("const", lambda limit: current != limit),
        ):
            if keyword in rule and invalid(rule[keyword]):
                raise ValueError(f"{path}: must satisfy {keyword} {rule[keyword]}")
        return current

    value = visit(value, schema, "analysis_policy")
    if complete:
        points = value["recommendations"]["effect_points"]
        if not points["not_shown"] < points["local"] < points["substantial"]:
            raise ValueError("analysis_policy.recommendations.effect_points: require not_shown < local < substantial")
        points = value["investigation"]["family_points"]
        if points["limited"] > points["usable"]:
            raise ValueError("analysis_policy.investigation.family_points: limited must not exceed usable")
    return value


def merge_policy(defaults, overrides, *, schema=None):
    defaults = validate_policy(defaults, complete=True, schema=schema)
    overrides = validate_policy(overrides, schema=schema)

    def merge(base, changes):
        result = deepcopy(base)
        for key, value in changes.items():
            result[key] = merge(base[key], value) if isinstance(value, dict) else value
        return result

    return validate_policy(merge(defaults, overrides), complete=True, schema=schema)


def load_policy(repository=None):
    schema = read_json(ASSETS / "analysis-policy.schema.json")
    defaults = read_json(ASSETS / "analysis-policy.json")
    overrides = {}
    if repository is not None:
        path = Path(repository).resolve() / PROJECT_POLICY
        if path.exists():
            overrides = read_json(path)
    return merge_policy(defaults, overrides, schema=schema)
