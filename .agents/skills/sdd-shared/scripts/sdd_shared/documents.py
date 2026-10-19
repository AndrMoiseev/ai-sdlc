"""Strict YAML and CommonMark record parsing; never execute document content."""
from dataclasses import dataclass
from pathlib import Path
import re

import yaml
from markdown_it import MarkdownIt


class ValidationError(ValueError):
    def __init__(self, code, message, path="", element_id=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.path, self.element_id = str(path), element_id


class InputError(ValidationError):
    """The requested check could not be performed."""


SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
MAX_YAML_CHARS = 1_000_000
MAX_DOCUMENT_CHARS = 4_000_000
MAX_YAML_DEPTH = 64
MAX_YAML_TOKENS = 100_000


def valid_slug(value):
    return isinstance(value, str) and 1 <= len(value) <= 64 and bool(SLUG.fullmatch(value))


def valid_id(value, prefix):
    return isinstance(value, str) and value.startswith(prefix + "-") and valid_slug(value[len(prefix) + 1:])


def safe_yaml(text):
    if len(text) > MAX_YAML_CHARS:
        raise ValidationError("yaml_limit", "YAML exceeds the 1,000,000 character limit")
    try:
        depth = 0
        for count, token in enumerate(yaml.scan(text), 1):
            if count > MAX_YAML_TOKENS:
                raise ValidationError("yaml_limit", "YAML exceeds the 100,000 token limit")
            if isinstance(token, (yaml.tokens.BlockMappingStartToken, yaml.tokens.BlockSequenceStartToken, yaml.tokens.FlowMappingStartToken, yaml.tokens.FlowSequenceStartToken)):
                depth += 1
                if depth > MAX_YAML_DEPTH:
                    raise ValidationError("yaml_limit", "YAML nesting exceeds 64 levels")
            elif isinstance(token, (yaml.tokens.BlockEndToken, yaml.tokens.FlowMappingEndToken, yaml.tokens.FlowSequenceEndToken)):
                depth -= 1
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken)):
                raise ValidationError("unsafe_yaml", "YAML aliases, anchors and explicit tags are forbidden")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        def inspect(current):
            if isinstance(current, yaml.MappingNode):
                keys = set()
                for key, value in current.value:
                    if not isinstance(key, yaml.ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                        raise ValidationError("yaml_key", "Mapping keys must be strings; merge keys are forbidden")
                    if key.value in keys:
                        raise ValidationError("duplicate_key", f"Duplicate YAML key: {key.value}")
                    keys.add(key.value)
                    inspect(value)
            elif isinstance(current, yaml.SequenceNode):
                for value in current.value:
                    inspect(value)
        inspect(node)
        try:
            value = yaml.safe_load(text)
        except (ValueError, OverflowError) as exc:
            # SafeLoader's timestamp/int constructors can raise builtin errors.
            raise ValidationError("invalid_yaml", f"Invalid YAML scalar: {exc}") from exc
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValidationError("invalid_yaml", str(exc)) from exc
    if not isinstance(value, dict):
        raise ValidationError("yaml_mapping", "Expected a YAML mapping")
    return value


def parse_markdown(text):
    """Bound parser work and recursion for both normative and baseline documents."""
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ValidationError("document_limit", "Document exceeds the 4,000,000 character limit")
    try:
        return MarkdownIt("commonmark", {"maxNesting": 64}).parse(text)
    except RecursionError as exc:
        raise ValidationError("markdown_limit", "Markdown nesting exceeds parser capacity") from exc


@dataclass
class Document:
    path: Path
    meta: dict
    records: list[dict]


FIELDS = {
    "requirement": ({"operation"}, {"source"}, "REQ"),
    "acceptance": ({"requirement", "conditions", "expected"}, set(), "AC"),
    "decision": ({"requirements"}, set(), "DEC"),
    "task": ({"number", "covers", "depends_on", "status", "verification"}, {"cannot_parallel_with"}, "TASK"),
}
KINDS = {"proposal": set(), "spec": {"requirement", "acceptance"}, "design": {"decision"}, "tasks": {"task"}}


def read_document(path):
    path = Path(path)
    try:
        with path.open(encoding="utf-8-sig") as stream:
            text = stream.read(MAX_DOCUMENT_CHARS + 1)
    except (OSError, UnicodeError) as exc:
        raise InputError("unreadable_input", str(exc), path) from exc
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ValidationError("document_limit", "Document exceeds the 4,000,000 character limit", path)
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValidationError("frontmatter", "Document must start with YAML frontmatter", path)
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValidationError("frontmatter", "Unterminated frontmatter", path)
    try:
        meta = safe_yaml("".join(lines[1:end]))
        if type(meta.get("schema_version")) is not int or meta["schema_version"] != 1:
            raise InputError("unsupported_version", "Only schema_version: 1 is supported", path)
        # Lens indexes have only schema_version/lenses; callers validate generic schemas.
        kind = meta.get("document_type", "")
        if not isinstance(kind, str):
            raise ValidationError("document_type", "document_type must be a string")
        if kind in KINDS:
            required = {"schema_version", "document_type", "change_id", "language"}
            if kind == "spec":
                required.add("capability")
            if set(meta) != required:
                raise ValidationError("document_fields", f"Expected fields: {sorted(required)}")
            if not valid_slug(meta["change_id"]) or not isinstance(meta["language"], str) or not meta["language"].strip():
                raise ValidationError("document_metadata", "Invalid change_id or language")
            if kind == "spec" and (not isinstance(meta["capability"], str) or not all(valid_slug(x) for x in meta["capability"].split("/"))):
                raise ValidationError("capability", "Invalid capability path")
        tokens = parse_markdown("".join(lines[end + 1:]))
        records, seen = [], set()
        parent_requirement = None
        positions = []
        for i, token in enumerate(tokens):
            if token.type == "heading_open" and token.level == 0:
                if token.tag in {"h1", "h2"}:
                    parent_requirement = None
            if token.type != "fence" or token.info.strip() != "yaml":
                continue
            try:
                record = safe_yaml(token.content)
            except ValidationError as exc:
                if exc.code == "yaml_mapping":
                    continue
                raise
            if "sdd_record" not in record:
                continue
            spec_requirement = kind == "spec" and record.get("sdd_record") == "requirement"
            allowed_headings = {"h2", "h3"} if spec_requirement else {"h3"}
            if i < 3 or tokens[i - 1].type != "heading_close" or tokens[i - 1].tag not in allowed_headings or token.level != 0:
                raise ValidationError("record_position", "A record must immediately follow a level-three heading (level two is allowed for spec requirements)")
            if token.map[0] > tokens[i - 3].map[1] + 1:
                raise ValidationError("record_position", "Only a blank line may separate heading and record")
            rid, record_kind = record.get("id"), record.get("sdd_record")
            if not isinstance(rid, str) or rid in seen:
                raise ValidationError("duplicate_id", f"Missing or duplicate ID: {rid}")
            seen.add(rid)
            if kind in KINDS:
                if not isinstance(record_kind, str) or record_kind not in KINDS[kind]:
                    raise ValidationError("record_type", f"Record {record_kind} is not allowed in {kind}", element_id=rid)
                required, optional, prefix = FIELDS[record_kind]
                required = required | {"sdd_record", "id"}
                if not required <= record.keys() or record.keys() - required - optional:
                    raise ValidationError("record_fields", f"Invalid fields for {record_kind}", element_id=rid)
                if not valid_id(rid, prefix):
                    raise ValidationError("invalid_id", f"Invalid {prefix} ID: {rid}", element_id=rid)
            heading = tokens[i - 1].tag
            positions.append((record, heading, parent_requirement))
            if spec_requirement and heading == "h2":
                parent_requirement = rid
            records.append(record)
        # Legacy v1 specs have only h3 records. New specs use h2 requirements.
        if kind == "spec" and any(heading == "h2" for _, heading, _ in positions):
            for record, heading, parent in positions:
                if record["sdd_record"] == "requirement" and heading != "h2":
                    raise ValidationError("record_position", "Use level-two headings for all requirements in a nested spec", element_id=record["id"])
                if record["sdd_record"] == "acceptance" and (parent is None or record["requirement"] != parent):
                    raise ValidationError("acceptance_parent", "Nested acceptance must reference its enclosing requirement", element_id=record["id"])
        return Document(path, meta, records)
    except ValidationError as exc:
        exc.path = exc.path or str(path)
        raise
