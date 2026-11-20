"""Check the detekt report profile against its supported host versions."""

import json
from pathlib import Path
import re

BIN = Path(__file__).resolve().parents[1] / "bin"
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*))?(?:\+[0-9A-Za-z.-]+)?")


def plugin_metadata():
    return json.loads((BIN / "plugins.json").read_text(encoding="utf-8"))


def version_key(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Unrecognized detekt version: {version!r}")
    major, minor, patch, prerelease = match.groups()
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part) for part in (prerelease or "").split("."))
    return (int(major), int(minor), int(patch), (0, identifiers) if prerelease else (1, ()))


def select_plugin(version):
    key = version_key(version)
    adapter = plugin_metadata()["adapters"].get(str(key[0]))
    if not adapter:
        raise ValueError(f"Unsupported detekt major {key[0]}; available measurement adapters: 1, 2")
    if key < version_key(adapter["minimum_version"]):
        raise ValueError(f"detekt {version} is below the adapter minimum {adapter['minimum_version']}")
    return adapter
