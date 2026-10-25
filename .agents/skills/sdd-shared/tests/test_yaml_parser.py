"""The accelerated and Python loaders retain the same strict input boundary."""
from datetime import date

import pytest
import yaml

from test_refactoring_documents import documents


@pytest.fixture(params=[yaml.SafeLoader, *([yaml.CSafeLoader] if hasattr(yaml, "CSafeLoader") else [])],
                ids=lambda loader: loader.__name__)
def parser(request, monkeypatch):
    monkeypatch.setattr(documents, "YAML_LOADER", request.param)
    return documents.safe_yaml


def test_constructs_values_from_the_verified_tree(parser):
    assert parser('text: "Привет"\nnumber: 0xff\nitems: [true, null]\ndate: 2026-10-25\n') == {
        "text": "Привет", "number": 255, "items": [True, None], "date": date(2026, 10, 25)}


@pytest.mark.parametrize("text,code", [
    ("key: 1\nkey: 2", "duplicate_key"),
    ("key: {nested: 1, nested: 2}", "duplicate_key"),
    ("1: value", "yaml_key"),
    ("root: {<<: {key: value}}", "yaml_key"),
    ("root: &anchor value", "unsafe_yaml"),
    ("root: *anchor", "unsafe_yaml"),
    ("root: !!str value", "unsafe_yaml"),
    ("root: !!python/object/apply:os.system ['echo unsafe']", "unsafe_yaml"),
    ("root: [", "invalid_yaml"),
    ("date: 2026-99-99", "invalid_yaml"),
    ("[]", "yaml_mapping"),
    ("", "yaml_mapping"),
    ("root: " + "[" * 65 + "0" + "]" * 65, "yaml_limit"),
])
def test_rejects_unsafe_or_invalid_input(parser, text, code):
    with pytest.raises(documents.ValidationError) as failure:
        parser(text)
    assert failure.value.code == code


def test_limits_size_and_tokens_before_construction(parser, monkeypatch):
    with pytest.raises(documents.ValidationError) as failure:
        parser("key: " + "x" * documents.MAX_YAML_CHARS)
    assert failure.value.code == "yaml_limit"
    monkeypatch.setattr(documents, "MAX_YAML_TOKENS", 4)
    with pytest.raises(documents.ValidationError) as failure:
        parser("key: [1, 2, 3]")
    assert failure.value.code == "yaml_limit"
